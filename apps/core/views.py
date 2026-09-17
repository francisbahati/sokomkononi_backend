from django.apps import apps
from rest_framework import permissions
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import SoftDeleteModel


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
                    "app": model._meta.app_label,
                    "model": model.__name__,
                    "count": count,
                })
        out.sort(key=lambda r: (-r["count"], r["model"]))
        return Response({"totals": out})