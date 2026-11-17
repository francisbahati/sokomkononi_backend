# apps/bundles/views_admin.py
"""
Admin — historia ya manunuzi ya bundles.

  GET /api/admin/bundles/purchases/        orodha (pagination + filters + summary)
  GET /api/admin/bundles/purchases/{id}/   undani

Filters (query params): bundle=<id>, user=<id>, status=PAID|PENDING|FAILED|REFUNDED,
search=<mnunuzi/barua pepe/simu/payment ref/bundle>, date_from=YYYY-MM-DD,
date_to=YYYY-MM-DD.

`summary` inahesabu kwa filters zilezile (si ukurasa mmoja tu): idadi, idadi
iliyolipwa, jumla ya kiasi kilicholipwa na credits zilizotolewa (zilizolipwa tu).
"""
from django.db.models import Count, Q, Sum
from django.utils.dateparse import parse_date
from rest_framework import viewsets
from rest_framework.exceptions import ValidationError
from rest_framework.response import Response

from apps.core.admin_2fa import IsAdminWith2FA

from .models import BundlePurchase
from .serializers_admin import AdminBundlePurchaseSerializer
from .stats import credits_total


def _int_param(params, name):
    raw = params.get(name)
    if raw in (None, ""):
        return None
    try:
        return int(raw)
    except (TypeError, ValueError):
        raise ValidationError({name: ["Lazima iwe namba."]})


def _date_param(params, name):
    raw = params.get(name)
    if not raw:
        return None
    parsed = parse_date(raw)
    if parsed is None:
        raise ValidationError({name: ["Tumia muundo YYYY-MM-DD."]})
    return parsed


class AdminBundlePurchaseViewSet(viewsets.GenericViewSet):
    serializer_class = AdminBundlePurchaseSerializer
    permission_classes = [IsAdminWith2FA]
    queryset = (
        BundlePurchase.objects
        .select_related("user", "bundle")
        .order_by("-created_at", "-id")
    )

    def _filtered(self, request):
        qs = self.get_queryset()
        p = request.query_params

        status_value = (p.get("status") or "").strip().upper()
        if status_value:
            if status_value not in BundlePurchase.Status.values:
                raise ValidationError({"status": ["Hali si sahihi."]})
            qs = qs.filter(status=status_value)

        bundle_id = _int_param(p, "bundle")
        if bundle_id is not None:
            qs = qs.filter(bundle_id=bundle_id)

        user_id = _int_param(p, "user")
        if user_id is not None:
            qs = qs.filter(user_id=user_id)

        date_from = _date_param(p, "date_from")
        if date_from:
            qs = qs.filter(created_at__date__gte=date_from)
        date_to = _date_param(p, "date_to")
        if date_to:
            qs = qs.filter(created_at__date__lte=date_to)

        search = (p.get("search") or "").strip()
        if search:
            qs = qs.filter(
                Q(user__name__icontains=search)
                | Q(user__email__icontains=search)
                | Q(user__phone__icontains=search)
                | Q(payment_reference__icontains=search)
                | Q(bundle__code__icontains=search)
                | Q(bundle__name_sw__icontains=search)
                | Q(bundle__name_en__icontains=search)
            )
        return qs

    def _summary(self, qs):
        paid = Q(status=BundlePurchase.Status.PAID)
        agg = qs.order_by().aggregate(
            count=Count("id"),
            paid_count=Count("id", filter=paid),
            paid_amount=Sum("amount", filter=paid),
        )
        issued = sum(
            credits_total(snap)
            for snap in qs.filter(paid)
            .order_by()
            .values_list("credits_snapshot", flat=True)
            .iterator()
        )
        return {
            "count": agg["count"] or 0,
            "paidCount": agg["paid_count"] or 0,
            "paidAmount": float(agg["paid_amount"] or 0),
            "creditsIssued": issued,
        }

    def list(self, request):
        qs = self._filtered(request)
        summary = self._summary(qs)
        page = self.paginate_queryset(qs)
        serializer = AdminBundlePurchaseSerializer(
            page if page is not None else qs, many=True,
        )
        if page is not None:
            response = self.get_paginated_response(serializer.data)
            response.data["summary"] = summary
            return response
        return Response({"results": serializer.data, "summary": summary})

    def retrieve(self, request, pk=None):
        return Response(AdminBundlePurchaseSerializer(self.get_object()).data)
