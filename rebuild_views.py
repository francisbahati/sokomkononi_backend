import re
import ast
import shutil
from datetime import datetime

PATH = "apps/listings/views.py"
BACKUP = f"apps/listings/views.py.bak_{datetime.now().strftime('%Y%m%d_%H%M%S')}"

# Backup
shutil.copy(PATH, BACKUP)
print(f"Backup: {BACKUP}")

with open(PATH, "r", encoding="utf-8") as f:
    content = f.read()

# ── Tafuta mstari mmoja mrefu (corrupted) ─────────────────
# Kama kuna mstari mrefu sana wenye `def similar` na `def destroy`,
# tunahitaji kuirekebisha.
lines = content.split("\n")
new_lines = []

for line in lines:
    # Kama mstari ni mrefu sana (> 500 chars) na una `def similar`
    if len(line) > 500 and "def similar" in line and "def destroy" in line:
        print(f"Imepatikana mstari corrupted: {len(line)} chars")
        
        # Gawanya kwa `    def similar` na `    def destroy`
        # Tafuta mahali pa kugawanya
        idx_similar = line.find("    def similar")
        idx_destroy = line.find("    # ═══")
        
        if idx_similar >= 0 and idx_destroy > idx_similar:
            similar_part = line[idx_similar:idx_destroy].rstrip()
            destroy_part = line[idx_destroy:].rstrip()
            
            # Gawanya similar_part kwa mistari
            # Inaonekana `def similar(self, request, pk=None):        """        Rudisha...`
            # Tunahitaji kuweka `\n` baada ya `):` na baada ya `"""` n.k.
            
            # Rekebisha similar_part — weka newlines
            similar_part = similar_part.replace(":        ", ":\n        ")
            similar_part = similar_part.replace(":            ", ":\n            ")
            similar_part = similar_part.replace(":                ", ":\n                ")
            similar_part = similar_part.replace('"        ', '"\n        ')
            similar_part = similar_part.replace(')        ', ')\n        ')
            similar_part = similar_part.replace(']        ', ']\n        ')
            similar_part = similar_part.replace('}        ', '}\n        ')
            similar_part = similar_part.replace(':        ', ':\n        ')
            
            # Hii ni ngumu. Badala yake, tuandike upya similar() na destroy()
            # tukiwa na indentation sahihi.
            similar_part = '''    def similar(self, request, pk=None):
        """
        Rudisha listings zinazofanana na listing hii.
        """
        listing = self.get_object()

        base = Listing.objects.filter(
            category=listing.category,
            status=Listing.Status.AVAILABLE,
        ).exclude(
            pk=listing.pk,
        ).select_related(
            "seller", "category",
        ).prefetch_related(
            "images",
        )

        results = []

        # 1. Category + location + price
        qs = base
        if listing.location:
            location_keyword = listing.location.split(",")[0].strip()
            if location_keyword:
                qs = qs.filter(location__icontains=location_keyword)

        if listing.price:
            try:
                price = float(listing.price)
                qs = qs.filter(
                    price__gte=price * 0.7,
                    price__lte=price * 1.3,
                )
            except (TypeError, ValueError):
                pass

        results = list(qs.order_by("-is_featured", "-created_at")[:8])

        # 2. Ondoa location, jaribu price pekee
        if not results and listing.price:
            try:
                price = float(listing.price)
                qs2 = base.filter(
                    price__gte=price * 0.7,
                    price__lte=price * 1.3,
                )
                results = list(
                    qs2.order_by("-is_featured", "-created_at")[:8]
                )
            except (TypeError, ValueError):
                pass

        # 3. Category pekee
        if not results:
            results = list(
                base.order_by("-is_featured", "-created_at")[:8]
            )

        serializer = ListingListSerializer(
            results, many=True, context={"request": request},
        )
        return Response(serializer.data)
'''
            
            # Gawanya destroy_part kwa mistari kwa kutumia `#`
            # Hii ni ngumu. Tuandike upya destroy() nzima.
            destroy_part = '''    def destroy(self, request, *args, **kwargs):
        listing = self.get_object()

        is_hard = request.query_params.get(
            "hard", "false"
        ).lower() in ("true", "1", "yes")

        # Soft delete (default)
        if not (request.user.is_staff and is_hard):
            listing.delete(
                by=request.user,
                reason=request.data.get("reason", "") if isinstance(
                    request.data, dict
                ) else "",
            )
            return Response(
                {
                    "detail": (
                        "Tangazo limewekwa kwenye kikapu. "
                        "Litaondolewa kabisa baada ya siku 90."
                    )
                },
                status=status.HTTP_200_OK,
            )

        # HARD DELETE
        try:
            with transaction.atomic():
                # 1. ListingFee (PROTECT)
                ListingFee.objects.filter(listing=listing).delete()

                # 2. Leads (PROTECT) -- HARD DELETE
                try:
                    from apps.leads.models import Lead

                    lead_ids = list(
                        Lead._base_manager
                        .filter(listing=listing)
                        .values_list("pk", flat=True)
                    )

                    for lead_id in lead_ids:
                        lead = Lead._base_manager.get(pk=lead_id)
                        if hasattr(lead, "hard_delete"):
                            lead.hard_delete()
                        else:
                            Lead._base_manager.filter(pk=lead_id).delete()

                    remaining = Lead._base_manager.filter(
                        listing=listing
                    ).count()
                    if remaining:
                        raise RuntimeError(
                            f"Leads {remaining} zinarejelea tangazo "
                            f"hili bado."
                        )
                except ImportError:
                    logger.warning(
                        "[listings] leads app not available, skipping"
                    )

                # 3. Transaction chain
                try:
                    from apps.transactions.models import (
                        Transaction,
                        Reservation,
                        InspectionPeriod,
                    )

                    tx_ids = list(
                        Transaction._base_manager
                        .filter(listing=listing)
                        .values_list("id", flat=True)
                    )

                    if tx_ids:
                        InspectionPeriod._base_manager.filter(
                            transaction_id__in=tx_ids,
                        ).delete()

                        Reservation._base_manager.filter(
                            transaction_id__in=tx_ids,
                        ).delete()

                        Transaction._base_manager.filter(
                            listing=listing,
                        ).delete()
                except ImportError:
                    logger.warning(
                        "[listings] transactions app not available, "
                        "skipping"
                    )

                # 4. DealRoom (PROTECT)
                try:
                    from apps.deals.models import DealRoom

                    DealRoom._base_manager.filter(
                        listing=listing,
                    ).delete()
                except ImportError:
                    logger.warning(
                        "[listings] deals app not available, skipping"
                    )

                # 5. Conversations + Messages
                try:
                    from apps.messaging.models import Conversation, Msg

                    conv_ids = list(
                        Conversation._base_manager
                        .filter(listing=listing)
                        .values_list("id", flat=True)
                    )

                    if conv_ids:
                        for msg in Msg._base_manager.filter(conversation_id__in=conv_ids):
                            if hasattr(msg, "hard_delete"):
                                msg.hard_delete()
                            else:
                                Msg._base_manager.filter(pk=msg.pk).delete()

                        for conv in Conversation._base_manager.filter(id__in=conv_ids):
                            if hasattr(conv, "hard_delete"):
                                conv.hard_delete()
                            else:
                                Conversation._base_manager.filter(pk=conv.pk).delete()
                except ImportError:
                    logger.warning("[listings] messaging app not available, skipping")

                # 6. Related models zingine
                related_fields = [
                    "images",
                    "boosts",
                    "waiting_list_entries",
                    "saved_by",
                    "search_matches",
                    "banner_ads",
                    "leading_purchases",
                ]

                for field_name in related_fields:
                    manager = getattr(listing, field_name, None)
                    if manager is None:
                        continue
                    try:
                        for obj in manager.all():
                            if hasattr(obj, "hard_delete"):
                                obj.hard_delete()
                            else:
                                obj.delete()
                    except Exception as exc:
                        logger.warning(
                            "[listings] delete %s for listing %s "
                            "failed: %s",
                            field_name, listing.id, exc,
                        )
                        raise

                # 7. Details (one-to-one)
                detail_fields = [
                    "property_details",
                    "land_details",
                    "vehicle_details",
                    "business_details",
                    "equipment_details",
                ]
                for field_name in detail_fields:
                    try:
                        obj = getattr(listing, field_name, None)
                    except Exception:
                        obj = None
                    if obj is not None:
                        obj.delete()

                # 8. Hatimaye: hard delete listing
                listing.hard_delete()

        except ProtectedError as exc:
            protected = list(getattr(exc, "protected_objects", []))
            logger.error(
                "[listings] ProtectedError on hard_delete for %s: %s",
                listing.id, protected,
            )
            return Response(
                {
                    "detail": (
                        "Imeshindwa kufuta: kuna rekodi "
                        f"{len(protected)} zinazorejelea tangazo "
                        "hili."
                    ),
                    "protected_objects": [
                        str(o) for o in protected
                    ],
                },
                status=status.HTTP_400_BAD_REQUEST,
            )
        except Exception as exc:
            logger.exception(
                "[listings] hard_delete failed for %s: %s",
                listing.id, exc,
            )
            return Response(
                {"detail": f"Imeshindwa kufuta: {exc}"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        return Response(
            {"detail": "Tangazo limefutwa kabisa."},
            status=status.HTTP_204_NO_CONTENT,
        )
'''
            
            new_lines.append(similar_part)
            new_lines.append("")
            new_lines.append(destroy_part)
        else:
            new_lines.append(line)
    else:
        new_lines.append(line)

content = "\n".join(new_lines)

with open(PATH, "w", encoding="utf-8") as f:
    f.write(content)

# Thibitisha syntax
try:
    ast.parse(content)
    print("OK — syntax ni sahihi")
except SyntaxError as e:
    print(f"KOSA: {e}")
    print(f"Rejesha: copy {BACKUP} {PATH}")