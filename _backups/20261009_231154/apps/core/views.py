from django.apps import apps
from django.db import transaction
from django.db.models import ProtectedError
from rest_framework import permissions, status
from rest_framework.response import Response
from rest_framework.views import APIView

from .constants import AUDIT_PROTECTED_MODEL_NAMES
from .models import SoftDeleteModel


# ----------------------------------------------------------------
# Audit helper — used by every destructive trash action
# ----------------------------------------------------------------
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
    return (model._meta.app_label, model.__name__) in AUDIT_PROTECTED_MODEL_NAMES


# ----------------------------------------------------------------
# Trash list presentation helpers
# ----------------------------------------------------------------
def _build_subtitle(model, obj):
    """
    Rudisha subtitle mafupi kutoka fields za kawaida.
    Inajaribu: title, name, subject, email, description, location,
    price — kwa mpangilio huo.
    """
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

    # Fallback: price kama ipo
    try:
        price = getattr(obj, "price", None)
        if price is not None:
            return f"TZS {price}"
    except Exception:
        pass
    return ""


def _build_deleted_by_name(obj):
    """Jina la mtumiaji aliyeifuta — kutoka `deleted_by` (FK au id)."""
    user = None
    try:
        user = getattr(obj, "deleted_by", None)
    except Exception:
        user = None

    if not user:
        return None

    # Kama `deleted_by` ni FK object (User)
    name = getattr(user, "name", None)
    if name:
        return name

    email = getattr(user, "email", None)
    if email:
        return email

    # Kama ni integer ID pekee — tafuta User
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
    """URL ya picha — kutoka fields za kawaida za ImageField."""
    for field in (
        "image", "avatar", "thumbnail", "photo",
        "logo", "banner", "cover",
    ):
        try:
            f = getattr(obj, field, None)
        except Exception:
            f = None
        if f and hasattr(f, "url"):
            try:
                return f.url
            except Exception:
                pass
    return None


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
                "protected": _is_protected(model),
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
            results.append({
                "id": obj.pk,
                "type": type,
                "name": str(obj),
                "subtitle": _build_subtitle(model, obj),
                "deleted_at": getattr(obj, "deleted_at", None),
                "deleted_by": getattr(obj, "deleted_by_id", None),
                "deleted_by_name": _build_deleted_by_name(obj),
                "reason": getattr(obj, "deletion_reason", "") or "",
                "details": getattr(obj, "deletion_reason", "") or "",
                "thumbnail": _build_thumbnail(obj),
                "repr": str(obj),
            })

        return Response({
            "type": type,
            "count": qs.count(),
            "protected": _is_protected(model),
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
        model = _resolve_model(type)
        if not model or not issubclass(model, SoftDeleteModel):
            return Response(
                {"detail": "Aina ya kikapu haipatikani."},
                status=status.HTTP_404_NOT_FOUND,
            )
        if _is_protected(model):
            return Response(
                {"detail": "Aina hii ya rekodi inalindwa dhidi ya kufutwa kabisa."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        obj = model.all_objects.filter(pk=pk, is_deleted=True).first()
        if not obj:
            return Response(
                {"detail": "Haipatikani kwenye kikapu."},
                status=status.HTTP_404_NOT_FOUND,
            )
        try:
            with transaction.atomic():
                _audit(
                    request, "trash.hard_deleted", model, obj.pk,
                    f"Hard-deleted {model.__name__}#{obj.pk}",
                )
                obj.hard_delete()
        except ProtectedError:
            return Response(
                {"detail": "Haifutiki — inatumika mahali pengine."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        return Response(status=status.HTTP_204_NO_CONTENT)


class TrashEmptyByTypeView(APIView):
    permission_classes = [permissions.IsAdminUser]

    def post(self, request, type):
        model = _resolve_model(type)
        if not model or not issubclass(model, SoftDeleteModel):
            return Response(
                {"detail": "Aina ya kikapu haipatikani."},
                status=status.HTTP_404_NOT_FOUND,
            )
        if _is_protected(model):
            return Response(
                {"detail": "Aina hii ya rekodi haiwezi kufutwa kabisa."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        deleted = skipped = 0
        for obj in model.all_objects.filter(is_deleted=True).iterator():
            try:
                with transaction.atomic():
                    _audit(
                        request, "trash.hard_deleted", model, obj.pk,
                        f"Empty-by-type: {model.__name__}#{obj.pk}",
                    )
                    obj.hard_delete()
                deleted += 1
            except ProtectedError:
                skipped += 1
        return Response({"deleted": deleted, "skipped": skipped})


class TrashEmptyAllView(APIView):
    permission_classes = [permissions.IsAdminUser]

    def post(self, request):
        body = request.data if isinstance(request.data, dict) else {}
        if body.get("confirm") != "DELETE ALL":
            return Response({
                "detail": (
                    'Tuma {"confirm": "DELETE ALL"} ili kuthibitisha. '
                    "Operesheni hii haiwezi kurudishwa."
                )
            }, status=status.HTTP_400_BAD_REQUEST)

        deleted = skipped = blocked = 0
        for model in apps.get_models():
            if not issubclass(model, SoftDeleteModel) or model._meta.abstract:
                continue
            if _is_protected(model):
                blocked += 1
                continue
            for obj in model.all_objects.filter(is_deleted=True).iterator():
                try:
                    with transaction.atomic():
                        _audit(
                            request, "trash.hard_deleted", model, obj.pk,
                            f"Empty-all: {model.__name__}#{obj.pk}",
                        )
                        obj.hard_delete()
                    deleted += 1
                except ProtectedError:
                    skipped += 1
        return Response({
            "deleted": deleted,
            "skipped": skipped,
            "protected_models": blocked,
        })