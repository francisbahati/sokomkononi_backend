# ============================================================
# apps/trash/views.py
#
# ✅ PROTECTION IMEONDOLWA KABISA
#    - Kila admin (is_staff) anaweza kufuta kila kitu
#    - Hakuna check ya _is_protected
#    - force ni True kila mara
#
# ✅ FIX: _cascade_protected inatumia hasattr(rel, "hard_delete")
#    badala ya isinstance(rel, SoftDeleteModel) — Transaction,
#    ListingFee, Reservation hazina hard_delete() → AttributeError
# ============================================================
from django.apps import apps
from django.db import transaction
from django.db.models import ProtectedError
from rest_framework import permissions, status
from rest_framework.response import Response
from rest_framework.views import APIView

from .constants import AUDIT_PROTECTED_MODEL_NAMES  # kept for compat (haijatumika)
from .models import SoftDeleteModel


def _audit(request, action, model, pk, details):
    try:
        from apps.audit.services.audit import log_action
        log_action(
            request=request,
            action=action,
            target=model.__name__,
            target_id=pk,
            details=details,
        )
    except Exception:
        import logging
        logging.getLogger(__name__).exception(
            "trash audit log failed for %s#%s", model.__name__, pk,
        )


def _resolve_model(type_str):
    if not type_str:
        return None
    if "." in type_str:
        app_label, _, model_name = type_str.partition(".")
        for candidate in (model_name, model_name.lower()):
            try:
                return apps.get_model(app_label, candidate)
            except LookupError:
                continue
    needle = type_str.lower()
    for model in apps.get_models():
        lname = model._meta.model_name
        if needle in (lname, lname + "s", model.__name__.lower()):
            return model
    if needle.endswith("s"):
        singular = needle[:-1]
        for model in apps.get_models():
            if model._meta.model_name == singular:
                return model
    return None


def _is_protected(model):
    """✅ Inarudisha `False` kila mara — protection imeondolewa."""
    return False


def _wants_force(request):
    """
    ✅ PROTECTION IMEONDOLWA: `force` ni `True` kila mara
    kwa admin (is_staff) au superuser.
    """
    user = request.user
    if not user or not user.is_authenticated:
        return False
    if not (user.is_staff or user.is_superuser):
        return False
    return True


def _hard_delete_obj(obj):
    """
    ✅ FIX: Futa object moja (hard) — inatumia `hasattr` badala ya
    `isinstance(obj, SoftDeleteModel)`.

    Sababu: `Transaction`, `ListingFee`, `Reservation`, n.k. ni
    SoftDeleteModel au la, lakini `hard_delete()` inaweza kuwa
    haijafafanuliwa au imeoverride — hivyo `hasattr` ni salama zaidi.
    """
    if hasattr(obj, "hard_delete") and callable(getattr(obj, "hard_delete")):
        obj.hard_delete()
    else:
        obj.delete()


def _cascade_protected(obj, max_depth=5):
    """
    Futa related objects zinazozuia `obj` kufutwa (PROTECT FK).

    Inarudia hadi `max_depth` mara:
      1. Jaribu `_hard_delete_obj(obj)`.
      2. Kama ProtectedError, futa kila `protected_object`.
      3. Jaribu tena.

    Returns: (success: bool, removed: list[str], error: str|None)
    """
    import logging
    log = logging.getLogger(__name__)

    removed = []
    for attempt in range(max_depth):
        try:
            _hard_delete_obj(obj)
            return True, removed, None
        except ProtectedError as e:
            progressed = False
            for rel in e.protected_objects:
                rel_model = rel._meta.model
                label = f"{rel_model._meta.app_label}.{rel_model.__name__}#{rel.pk}"
                try:
                    # ✅ FIX: hasattr badala ya isinstance
                    _hard_delete_obj(rel)
                    removed.append(label)
                    progressed = True
                except ProtectedError:
                    ok, sub_removed, sub_err = _cascade_protected(
                        rel, max_depth - 1
                    )
                    if ok:
                        removed.extend(sub_removed)
                        removed.append(label)
                        progressed = True
                    else:
                        log.warning(
                            "[trash] cascade failed for %s: %s", label, sub_err
                        )
                        return False, removed, (
                            f"Imeshindwa kufuta {label}: {sub_err}"
                        )
                except Exception as inner:
                    log.exception(
                        "[trash] cascade exception for %s: %s", label, inner
                    )
                    return False, removed, (
                        f"Imeshindwa kufuta {label}: {inner}"
                    )
            if not progressed:
                return False, removed, (
                    "Bado imezuiliwa na: "
                    + ", ".join(str(o) for o in e.protected_objects)[:500]
                )
    try:
        _hard_delete_obj(obj)
        return True, removed, None
    except ProtectedError as e:
        return False, removed, (
            "Bado imezuiliwa na: "
            + ", ".join(str(o) for o in e.protected_objects)[:500]
        )
    except Exception as e:
        log.exception("[trash] final hard_delete failed: %s", e)
        return False, removed, f"Hitilafu: {e}"


def _build_subtitle(model, obj):
    for field in (
        "title", "name", "subject", "email",
        "description", "location", "address",
    ):
        try:
            val = getattr(obj, field, None)
        except Exception:
            val = None
        if val:
            text = str(val).strip()
            if text:
                return text[:200]
    try:
        price = getattr(obj, "price", None)
        if price is not None:
            return f"TZS {price}"
    except Exception:
        pass
    return ""


def _build_deleted_by_name(obj):
    user = None
    try:
        user = getattr(obj, "deleted_by", None)
    except Exception:
        user = None
    if not user:
        return None
    name = getattr(user, "name", None)
    if name:
        return name
    email = getattr(user, "email", None)
    if email:
        return email
    try:
        from django.contrib.auth import get_user_model
        User = get_user_model()
        u = User.objects.filter(pk=user).first()
        if u:
            return getattr(u, "name", None) or getattr(u, "email", None)
    except Exception:
        pass
    return None


def _build_thumbnail(obj):
    for field in (
        "image", "avatar", "thumbnail", "photo",
        "logo", "banner", "cover", "image_url",
    ):
        try:
            f = getattr(obj, field, None)
        except Exception:
            f = None
        if not f:
            continue
        if isinstance(f, str):
            return f
        if hasattr(f, "url"):
            try:
                return f.url
            except Exception:
                pass
    return None


def _format_protected(e):
    try:
        return [str(o) for o in e.protected_objects][:10]
    except Exception:
        return []


class TrashOverviewView(APIView):
    permission_classes = [permissions.IsAdminUser]

    def get(self, request):
        out = []
        for model in apps.get_models():
            if not issubclass(model, SoftDeleteModel) or model._meta.abstract:
                continue
            out.append({
                "type": f"{model._meta.app_label}.{model.__name__}",
                "app": model._meta.app_label,
                "model": model.__name__,
                "count": model.all_objects.filter(is_deleted=True).count(),
                # ✅ PROTECTION IMEONDOLWA — kila model inaruhusiwa
                "protected": False,
            })
        out.sort(key=lambda r: (-r["count"], r["model"]))
        return Response({"totals": out})


class TrashListView(APIView):
    permission_classes = [permissions.IsAdminUser]

    def get(self, request, type):
        model = _resolve_model(type)
        if not model or not issubclass(model, SoftDeleteModel):
            return Response(
                {"detail": "Aina ya kikapu haipatikani."},
                status=status.HTTP_404_NOT_FOUND,
            )

        qs = model.all_objects.filter(is_deleted=True).order_by("-deleted_at")

        results = []
        for obj in qs[:500]:
            subtitle = _build_subtitle(model, obj)
            results.append({
                "id": obj.pk,
                "type": type,
                "name": subtitle or str(obj),
                "subtitle": subtitle,
                "deleted_at": getattr(obj, "deleted_at", None),
                "deleted_by": getattr(obj, "deleted_by_id", None),
                "deleted_by_name": _build_deleted_by_name(obj),
                "reason": getattr(obj, "deletion_reason", "") or "",
                "details": getattr(obj, "deletion_reason", "") or "",
                "thumbnail": _build_thumbnail(obj),
                "repr": str(obj),
                # ✅ Kila item inaruhusiwa kufutwa
                "protected": False,
            })

        return Response({
            "type": type,
            "count": qs.count(),
            "protected": False,
            "results": results,
        })


class TrashRestoreView(APIView):
    permission_classes = [permissions.IsAdminUser]

    def post(self, request, type, pk):
        model = _resolve_model(type)
        if not model or not issubclass(model, SoftDeleteModel):
            return Response(
                {"detail": "Aina ya kikapu haipatikani."},
                status=status.HTTP_404_NOT_FOUND,
            )
        obj = model.all_objects.filter(pk=pk, is_deleted=True).first()
        if not obj:
            return Response(
                {"detail": "Haipatikani kwenye kikapu."},
                status=status.HTTP_404_NOT_FOUND,
            )
        obj.restore()
        _audit(
            request, "trash.restored", model, obj.pk,
            f"Restored {model.__name__}#{obj.pk}",
        )
        return Response({"detail": "Imerejeshwa."})


class TrashPermanentDeleteView(APIView):
    permission_classes = [permissions.IsAdminUser]

    def delete(self, request, type, pk):
        import logging
        log = logging.getLogger(__name__)

        model = _resolve_model(type)
        if not model or not issubclass(model, SoftDeleteModel):
            return Response(
                {"detail": "Aina ya kikapu haipatikani."},
                status=status.HTTP_404_NOT_FOUND,
            )

        obj = model.all_objects.filter(pk=pk, is_deleted=True).first()
        if not obj:
            return Response(
                {"detail": "Haipatikani kwenye kikapu."},
                status=status.HTTP_404_NOT_FOUND,
            )

        # ✅ PROTECTION IMEONDOLWA — force kila mara
        try:
            with transaction.atomic():
                _audit(
                    request, "trash.hard_deleted", model, obj.pk,
                    f"Hard-deleted {model.__name__}#{obj.pk} [FORCED]",
                )
                ok, removed, err = _cascade_protected(obj)
                if not ok:
                    transaction.set_rollback(True)
                    return Response(
                        {
                            "detail": (
                                err
                                or "Haifutiki — inatumika mahali pengine."
                            ),
                            "protected_objects": removed[:10] or [],
                        },
                        status=status.HTTP_400_BAD_REQUEST,
                    )
                if removed:
                    _audit(
                        request, "trash.cascade_deleted", model, obj.pk,
                        f"Cascade-deleted {len(removed)} related: "
                        + ", ".join(removed[:10]),
                    )
        except ProtectedError as e:
            return Response(
                {
                    "detail": "Haifutiki — inatumika mahali pengine.",
                    "protected_objects": _format_protected(e),
                },
                status=status.HTTP_400_BAD_REQUEST,
            )
        except Exception as e:
            log.exception(
                "[trash] permanent delete failed for %s#%s: %s",
                model.__name__, obj.pk, e,
            )
            return Response(
                {
                    "detail": f"Hitilafu ya mfumo: {e}",
                    "type": type,
                    "id": pk,
                },
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

        return Response(status=status.HTTP_204_NO_CONTENT)


class TrashEmptyByTypeView(APIView):
    permission_classes = [permissions.IsAdminUser]

    def post(self, request, type):
        import logging
        log = logging.getLogger(__name__)

        model = _resolve_model(type)
        if not model or not issubclass(model, SoftDeleteModel):
            return Response(
                {"detail": "Aina ya kikapu haipatikani."},
                status=status.HTTP_404_NOT_FOUND,
            )

        deleted = skipped = 0
        protected_objs = []
        for obj in model.all_objects.filter(is_deleted=True).iterator():
            try:
                with transaction.atomic():
                    _audit(
                        request, "trash.hard_deleted", model, obj.pk,
                        f"Empty-by-type: {model.__name__}#{obj.pk} [FORCED]",
                    )
                    ok, removed, err = _cascade_protected(obj)
                    if not ok:
                        transaction.set_rollback(True)
                        skipped += 1
                        protected_objs.extend(removed[:5] or [err])
                        continue
                    if removed:
                        _audit(
                            request, "trash.cascade_deleted", model, obj.pk,
                            f"Cascade-deleted {len(removed)} related",
                        )
                deleted += 1
            except ProtectedError as e:
                skipped += 1
                protected_objs.extend(_format_protected(e))
            except Exception as e:
                log.exception(
                    "[trash] empty-by-type failed for %s#%s: %s",
                    model.__name__, obj.pk, e,
                )
                skipped += 1
                protected_objs.append(f"{model.__name__}#{obj.pk}: {e}")
        return Response({
            "deleted": deleted,
            "skipped": skipped,
            "protected_objects": protected_objs[:10],
            "forced": True,
        })


class TrashEmptyAllView(APIView):
    permission_classes = [permissions.IsAdminUser]

    def post(self, request):
        import logging
        log = logging.getLogger(__name__)

        body = request.data if isinstance(request.data, dict) else {}
        if body.get("confirm") != "DELETE ALL":
            return Response({
                "detail": (
                    'Tuma {"confirm": "DELETE ALL"} ili kuthibitisha. '
                    "Operesheni hii haiwezi kurudishwa."
                )
            }, status=status.HTTP_400_BAD_REQUEST)

        deleted = skipped = 0
        for model in apps.get_models():
            if not issubclass(model, SoftDeleteModel) or model._meta.abstract:
                continue
            for obj in model.all_objects.filter(is_deleted=True).iterator():
                try:
                    with transaction.atomic():
                        _audit(
                            request, "trash.hard_deleted", model, obj.pk,
                            f"Empty-all: {model.__name__}#{obj.pk} [FORCED]",
                        )
                        ok, _removed, _err = _cascade_protected(obj)
                        if not ok:
                            transaction.set_rollback(True)
                            skipped += 1
                            continue
                    deleted += 1
                except ProtectedError:
                    skipped += 1
                except Exception as e:
                    log.exception(
                        "[trash] empty-all failed for %s#%s: %s",
                        model.__name__, obj.pk, e,
                    )
                    skipped += 1
        return Response({
            "deleted": deleted,
            "skipped": skipped,
            "protected_models": [],
            "forced": True,
        })