from django.apps import apps
from django.db.models import ProtectedError
from rest_framework import permissions, status
from rest_framework.response import Response
from rest_framework.views import APIView

from .constants import AUDIT_PROTECTED_MODEL_NAMES
from .models import SoftDeleteModel


def _resolve_model(type_str):
    """
    Accepts:
      - "Listing"              (exact model name)
      - "listing"              (lowercased)
      - "listings"             (plural lowercase)
      - "listings.Listing"     (app.Model)
      - "listings.listing"     (app.model lowercase)
    """
    if not type_str:
        return None

    # 1) app.Model / app.model
    if "." in type_str:
        app_label, _, model_name = type_str.partition(".")
        for candidate in (model_name, model_name.lower()):
            try:
                return apps.get_model(app_label, candidate)
            except LookupError:
                continue

    needle = type_str.lower()

    # 2) match on lowercase model name OR plural of it
    for model in apps.get_models():
        lname = model._meta.model_name           # e.g. "listing"
        plural = lname + "s"                     # e.g. "listings"
        if needle in (lname, plural, model.__name__.lower()):
            return model

    # 3) fallback: singularize trailing "s"
    if needle.endswith("s"):
        singular = needle[:-1]
        for model in apps.get_models():
            if model._meta.model_name == singular:
                return model

    return None


def _is_protected(model):
    return (model._meta.app_label, model.__name__) in AUDIT_PROTECTED_MODEL_NAMES


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
            return Response({"detail": "Aina ya kikapu haipatikani."},
                            status=status.HTTP_404_NOT_FOUND)
        qs = model.all_objects.filter(is_deleted=True).order_by("-deleted_at")
        out = []
        for obj in qs[:500]:
            out.append({
                "id": obj.pk,
                "deleted_at": getattr(obj, "deleted_at", None),
                "deleted_by": getattr(obj, "deleted_by_id", None),
                "reason": getattr(obj, "deletion_reason", ""),
                "repr": str(obj),
            })
        return Response({
            "type": type,
            "count": qs.count(),
            "protected": _is_protected(model),
            "results": out,
        })


class TrashRestoreView(APIView):
    permission_classes = [permissions.IsAdminUser]

    def post(self, request, type, pk):
        model = _resolve_model(type)
        if not model or not issubclass(model, SoftDeleteModel):
            return Response({"detail": "Aina ya kikapu haipatikani."},
                            status=status.HTTP_404_NOT_FOUND)
        obj = model.all_objects.filter(pk=pk, is_deleted=True).first()
        if not obj:
            return Response({"detail": "Haipatikani kwenye kikapu."},
                            status=status.HTTP_404_NOT_FOUND)
        obj.restore()
        return Response({"detail": "Imerejeshwa."})


class TrashPermanentDeleteView(APIView):
    permission_classes = [permissions.IsAdminUser]

    def delete(self, request, type, pk):
        model = _resolve_model(type)
        if not model or not issubclass(model, SoftDeleteModel):
            return Response({"detail": "Aina ya kikapu haipatikani."},
                            status=status.HTTP_404_NOT_FOUND)
        if _is_protected(model):
            return Response(
                {"detail": "Aina hii ya rekodi inalindwa dhidi ya kufutwa kabisa."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        obj = model.all_objects.filter(pk=pk, is_deleted=True).first()
        if not obj:
            return Response({"detail": "Haipatikani kwenye kikapu."},
                            status=status.HTTP_404_NOT_FOUND)
        try:
            obj.hard_delete()
        except ProtectedError:
            return Response({"detail": "Haifutiki — inatumika mahali pengine."},
                            status=status.HTTP_400_BAD_REQUEST)
        return Response(status=status.HTTP_204_NO_CONTENT)


class TrashEmptyByTypeView(APIView):
    permission_classes = [permissions.IsAdminUser]

    def post(self, request, type):
        model = _resolve_model(type)
        if not model or not issubclass(model, SoftDeleteModel):
            return Response({"detail": "Aina ya kikapu haipatikani."},
                            status=status.HTTP_404_NOT_FOUND)
        if _is_protected(model):
            return Response(
                {"detail": "Aina hii ya rekodi haiwezi kufutwa kabisa."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        deleted = skipped = 0
        for obj in model.all_objects.filter(is_deleted=True).iterator():
            try:
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
                "detail": ('Tuma {"confirm": "DELETE ALL"} ili kuthibitisha. '
                           "Operesheni hii haiwezi kurudishwa.")
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
                    obj.hard_delete()
                    deleted += 1
                except ProtectedError:
                    skipped += 1
        return Response({
            "deleted": deleted, "skipped": skipped, "protected_models": blocked,
        })
