from django.apps import apps
from django.db.models import ProtectedError
from rest_framework import permissions, status
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import SoftDeleteModel


def _resolve_model(type_str):
    """
    Accepts:
        - "category"
        - "categories.Category"
        - "categories.category"
    Returns the model class or None.
    """
    if not type_str:
        return None

    if "." in type_str:
        app_label, _, model_name = type_str.partition(".")
        try:
            return apps.get_model(app_label, model_name)
        except LookupError:
            pass
        # try again with lowercased model name
        try:
            return apps.get_model(app_label, model_name.lower())
        except LookupError:
            pass

    needle = type_str.lower()
    for model in apps.get_models():
        if (
            model._meta.model_name == needle
            or model.__name__.lower() == needle
        ):
            return model
    return None


class TrashOverviewView(APIView):
    permission_classes = [permissions.IsAdminUser]

    def get(self, request):
        out = []
        for model in apps.get_models():
            if (
                issubclass(model, SoftDeleteModel)
                and not model._meta.abstract
            ):
                count = model.all_objects.filter(is_deleted=True).count()
                out.append({
                    "type": f"{model._meta.app_label}.{model.__name__}",
                    "app": model._meta.app_label,
                    "model": model.__name__,
                    "count": count,
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
            "results": out,
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
        obj = model.all_objects.filter(pk=pk).first()
        if not obj:
            return Response(
                {"detail": "Haipatikani."},
                status=status.HTTP_404_NOT_FOUND,
            )
        try:
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
        deleted = 0
        skipped = 0
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
        # Require an explicit confirmation phrase so a stray click
        # cannot wipe every soft-deleted row across every app.
        body = request.data if isinstance(request.data, dict) else {}
        if body.get("confirm") != "DELETE ALL":
            return Response(
                {
                    "detail": (
                        'Tuma {"confirm": "DELETE ALL"} ili kuthibitisha. '
                        "Operesheni hii haiwezi kurudishwa."
                    )
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        deleted = 0
        skipped = 0
        for model in apps.get_models():
            if (
                not issubclass(model, SoftDeleteModel)
                or model._meta.abstract
            ):
                continue
            for obj in model.all_objects.filter(is_deleted=True).iterator():
                try:
                    obj.hard_delete()
                    deleted += 1
                except ProtectedError:
                    skipped += 1
        return Response({"deleted": deleted, "skipped": skipped})
