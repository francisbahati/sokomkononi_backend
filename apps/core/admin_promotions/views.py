# apps/core/admin_promotions/views.py
"""
Admin actions kwa promotions: pause, resume, cancel.
Inatumika kwa boost, leading, advertise, reservation.
"""
from django.utils import timezone
from rest_framework import permissions, status
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.core.permissions import IsAdminUser


# ============================================================
# MODEL MAP — kila promotion type ina model yake
# ============================================================
def _get_model(type_key):
    """Rudisha model class kwa type."""
    if type_key == "boost":
        from apps.boosting.models import ListingBoost
        return ListingBoost
    if type_key == "leading":
        from apps.leading_fees.models import ListingLeading
        return ListingLeading
    if type_key == "advertise":
        from apps.banners.models import BannerAd
        return BannerAd
    if type_key == "reservation":
        try:
            from apps.transactions.models import Reservation
            return Reservation
        except ImportError:
            return None
    if type_key == "extension":
        try:
            from apps.transactions.models import ReservationExtension
            return ReservationExtension
        except ImportError:
            return None
    return None


def _log(request, action, target, target_id, details):
    try:
        from apps.audit.services.audit import log_action
        log_action(
            request=request,
            action=action,
            target=target,
            target_id=target_id,
            details=details,
        )
    except Exception:
        import logging
        logging.getLogger(__name__).exception(
            "Failed to write audit log: %s", action,
        )


class AdminPromotionActionView(APIView):
    """
    POST /api/admin/promotions/{type}/{id}/pause/
    POST /api/admin/promotions/{type}/{id}/resume/
    POST /api/admin/promotions/{type}/{id}/cancel/
    
    type: "boost" | "leading" | "advertise" | "reservation" | "extension"

    "extension" (ada ya kuongeza muda): cancel + refund pekee. Pause/resume
    hazikubaliki kwa sababu status yake ni ya malipo (PENDING_PAYMENT/PAID...).
    """
    permission_classes = [IsAdminUser]

    def post(self, request, type, id, action):
        Model = _get_model(type)
        if not Model:
            return Response(
                {"detail": f"Promotion type '{type}' haipatikani."},
                status=status.HTTP_404_NOT_FOUND,
            )

        if type == "extension" and action in ("pause", "resume"):
            return Response(
                {"detail": "Extension haiwezi kusimamishwa wala kuwashwa."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        obj = Model.objects.filter(pk=id).first()
        if not obj:
            return Response(
                {"detail": "Promotion haipatikani."},
                status=status.HTTP_404_NOT_FOUND,
            )

        if action == "pause":
            return self._pause(request, obj, type)
        elif action == "resume":
            return self._resume(request, obj, type)
        elif action == "cancel":
            return self._cancel(request, obj, type)
        else:
            return Response(
                {"detail": f"Action '{action}' haijulikani."},
                status=status.HTTP_400_BAD_REQUEST,
            )

    def _pause(self, request, obj, type):
        """Simamisha promotion — inaondolewa kwenye rotation."""
        reason = (request.data.get("reason") or "").strip()

        if hasattr(obj, "paused_by_admin"):
            obj.paused_by_admin = True
            obj.admin_note = reason
            obj.save(update_fields=["paused_by_admin", "admin_note", "updated_at"])
        else:
            # Fallback kwa models zisizo na fields hizi
            if hasattr(obj, "active"):
                obj.active = False
                obj.save(update_fields=["active"])
            elif hasattr(obj, "status"):
                obj.status = "PAUSED"
                obj.save(update_fields=["status"])

        _log(
            request,
            action=f"promotion.{type}.paused",
            target=type.capitalize(),
            target_id=obj.pk,
            details=f"Paused {type} #{obj.pk}. Reason: {reason or '—'}",
        )

        return Response({
            "detail": f"{type.capitalize()} imesimamishwa.",
            "type": type,
            "id": obj.pk,
        })

    def _resume(self, request, obj, type):
        """Washa promotion tena — inarudi kwenye rotation."""
        note = (request.data.get("note") or "").strip()

        if hasattr(obj, "paused_by_admin"):
            obj.paused_by_admin = False
            obj.admin_note = note
            obj.save(update_fields=["paused_by_admin", "admin_note", "updated_at"])
        else:
            if hasattr(obj, "active"):
                obj.active = True
                obj.save(update_fields=["active"])
            elif hasattr(obj, "status"):
                obj.status = "ACTIVE"
                obj.save(update_fields=["status"])

        _log(
            request,
            action=f"promotion.{type}.resumed",
            target=type.capitalize(),
            target_id=obj.pk,
            details=f"Resumed {type} #{obj.pk}. Note: {note or '—'}",
        )

        return Response({
            "detail": f"{type.capitalize()} imewashwa.",
            "type": type,
            "id": obj.pk,
        })

    def _cancel(self, request, obj, type):
        """Futa promotion — na refund option."""
        reason = (request.data.get("reason") or "").strip()
        refund = bool(request.data.get("refund", False))

        if hasattr(obj, "active"):
            obj.active = False
        if hasattr(obj, "status"):
            obj.status = "CANCELLED"
        if hasattr(obj, "cancelled_at"):
            obj.cancelled_at = timezone.now()
        if hasattr(obj, "admin_note"):
            obj.admin_note = reason
        obj.save()

        # Refund — kama admin amechagua
        if refund:
            try:
                from apps.payments.refunds import refund_promotion
                refund_promotion(obj, type, reason)
            except Exception:
                import logging
                logging.getLogger(__name__).exception(
                    "Refund failed for %s #%s", type, obj.pk
                )

        _log(
            request,
            action=f"promotion.{type}.cancelled",
            target=type.capitalize(),
            target_id=obj.pk,
            details=(
                f"Cancelled {type} #{obj.pk}. "
                f"Refund: {refund}. Reason: {reason or '—'}"
            ),
        )

        return Response({
            "detail": f"{type.capitalize()} imefutwa.",
            "type": type,
            "id": obj.pk,
            "refunded": refund,
        })