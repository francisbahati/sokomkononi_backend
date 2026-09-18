from datetime import datetime, time, timedelta
from decimal import Decimal

from django.db.models import Sum
from django.db.models.functions import Coalesce
from django.utils import timezone

from apps.boosting.models import ListingBoost
from apps.listings.models import ListingFee
from apps.transactions.models import Reservation


ZERO = Decimal("0.00")


def get_period_range(period):
    now = timezone.localtime()

    if period == "today":
        start = datetime.combine(now.date(), time.min, tzinfo=now.tzinfo)
        end = start + timedelta(days=1)

    elif period == "week":
        start_date = now.date() - timedelta(days=now.weekday())
        start = datetime.combine(start_date, time.min, tzinfo=now.tzinfo)
        end = start + timedelta(days=7)

    elif period == "month":
        start_date = now.date().replace(day=1)
        start = datetime.combine(start_date, time.min, tzinfo=now.tzinfo)

        if start_date.month == 12:
            next_month = start_date.replace(
                year=start_date.year + 1, month=1, day=1,
            )
        else:
            next_month = start_date.replace(
                month=start_date.month + 1, day=1,
            )

        end = datetime.combine(next_month, time.min, tzinfo=now.tzinfo)

    elif period == "all":
        return None, None

    else:
        raise ValueError("Invalid period. Use: all, today, week, or month.")

    return start, end


def _apply_date_filter(queryset, start, end, field="created_at"):
    if start is None or end is None:
        return queryset
    return queryset.filter(**{
        f"{field}__gte": start, f"{field}__lt": end,
    })


def calculate_financial_dashboard(period="all"):
    start, end = get_period_range(period)

    # Listing Fees — use paid_at coalesced to created_at
    listing_fees = ListingFee.objects.filter(payment_status="PAID").annotate(
        effective_paid=Coalesce("paid_at", "created_at"),
    )
    if start and end:
        listing_fees = listing_fees.filter(
            effective_paid__gte=start, effective_paid__lt=end,
        )
    listing_fee_revenue = listing_fees.aggregate(
        total=Sum("amount"),
    )["total"] or ZERO
    paid_listing_fees = listing_fees.count()

    # Reservations
    reservations = Reservation.objects.filter(payment_status="PAID").annotate(
        effective_paid=Coalesce("paid_at", "created_at"),
    )
    if start and end:
        reservations = reservations.filter(
            effective_paid__gte=start, effective_paid__lt=end,
        )
    reservation_revenue = reservations.aggregate(
        total=Sum("deposit_amount"),
    )["total"] or ZERO
    paid_reservations = reservations.count()

    # Boosts
    boosts = ListingBoost.objects.filter(payment_status="PAID").annotate(
        effective_paid=Coalesce("paid_at", "created_at"),
    )
    if start and end:
        boosts = boosts.filter(
            effective_paid__gte=start, effective_paid__lt=end,
        )
    boosting_revenue = boosts.aggregate(total=Sum("amount"))["total"] or ZERO
    paid_boosts = boosts.count()

    # Refunds
    refunds = Reservation.objects.filter(payment_status="REFUNDED").annotate(
        effective_refund=Coalesce("refunded_at", "created_at"),
    )
    if start and end:
        refunds = refunds.filter(
            effective_refund__gte=start, effective_refund__lt=end,
        )
    refund_amount = refunds.aggregate(
        total=Sum("deposit_amount"),
    )["total"] or ZERO
    refund_count = refunds.count()

    # Placeholders for future revenue sources.
    advertisement_revenue = ZERO
    leading_revenue = ZERO

    total_revenue = (
        listing_fee_revenue
        + reservation_revenue
        + boosting_revenue
        + advertisement_revenue
        + leading_revenue
    )
    net_revenue = total_revenue - refund_amount

    return {
        "period": period,
        "start": start,
        "end": end,
        "total_revenue": total_revenue,
        "listing_fee_revenue": listing_fee_revenue,
        "reservation_revenue": reservation_revenue,
        "boosting_revenue": boosting_revenue,
        "advertisement_revenue": advertisement_revenue,
        "leading_revenue": leading_revenue,
        "refunds": refund_amount,
        "net_revenue": net_revenue,
        "paid_listing_fees": paid_listing_fees,
        "paid_reservations": paid_reservations,
        "paid_boosts": paid_boosts,
        "refund_count": refund_count,
    }


def get_revenue_records(period="all", source="all"):
    start, end = get_period_range(period)
    records = []

    if source in {"all", "listing_fee"}:
        qs = ListingFee.objects.filter(
            payment_status="PAID",
        ).select_related("seller", "listing").annotate(
            effective_paid=Coalesce("paid_at", "created_at"),
        )
        if start and end:
            qs = qs.filter(
                effective_paid__gte=start, effective_paid__lt=end,
            )
        for item in qs:
            records.append({
                "id": item.id,
                "source": "listing_fee",
                "source_label": "Listing Fee",
                "amount": item.amount,
                "payment_status": item.payment_status,
                "payment_reference": item.payment_reference,
                "paid_at": item.paid_at,
                "refunded_at": None,
                "seller_id": item.seller_id,
                "seller_name": getattr(item.seller, "name", ""),
                "seller_email": getattr(item.seller, "email", "") or "",
                "listing_id": item.listing_id,
                "listing_title": getattr(item.listing, "title", ""),
                "status": None,
                "created_at": item.created_at,
            })

    if source in {"all", "reservation"}:
        qs = Reservation.objects.filter(
            payment_status="PAID",
        ).select_related(
            "transaction", "transaction__seller", "transaction__listing",
        ).annotate(
            effective_paid=Coalesce("paid_at", "created_at"),
        )
        if start and end:
            qs = qs.filter(
                effective_paid__gte=start, effective_paid__lt=end,
            )
        for item in qs:
            transaction = item.transaction
            seller = transaction.seller
            listing = transaction.listing
            records.append({
                "id": item.id,
                "source": "reservation",
                "source_label": "Reservation Deposit",
                "amount": item.deposit_amount,
                "payment_status": item.payment_status,
                "payment_reference": item.payment_reference,
                "paid_at": item.paid_at,
                "refunded_at": None,
                "seller_id": seller.id if seller else None,
                "seller_name": getattr(seller, "name", "") if seller else "",
                "seller_email": (
                    (getattr(seller, "email", "") or "") if seller else ""
                ),
                "listing_id": listing.id if listing else None,
                "listing_title": (
                    getattr(listing, "title", "") if listing else ""
                ),
                "status": item.status,
                "created_at": item.created_at,
            })

    if source in {"all", "boosting"}:
        qs = ListingBoost.objects.filter(
            payment_status="PAID",
        ).select_related("seller", "listing", "package").annotate(
            effective_paid=Coalesce("paid_at", "created_at"),
        )
        if start and end:
            qs = qs.filter(
                effective_paid__gte=start, effective_paid__lt=end,
            )
        for item in qs:
            records.append({
                "id": item.id,
                "source": "boosting",
                "source_label": "Boosting Fee",
                "amount": item.amount,
                "payment_status": item.payment_status,
                "payment_reference": item.payment_reference,
                "paid_at": item.paid_at,
                "refunded_at": None,
                "seller_id": item.seller_id,
                "seller_name": getattr(item.seller, "name", ""),
                "seller_email": getattr(item.seller, "email", "") or "",
                "listing_id": item.listing_id,
                "listing_title": getattr(item.listing, "title", ""),
                "status": item.status,
                "created_at": item.created_at,
            })

    if source in {"all", "refund"}:
        qs = Reservation.objects.filter(
            payment_status="REFUNDED",
        ).select_related(
            "transaction", "transaction__seller", "transaction__listing",
        ).annotate(
            effective_refund=Coalesce("refunded_at", "created_at"),
        )
        if start and end:
            qs = qs.filter(
                effective_refund__gte=start, effective_refund__lt=end,
            )
        for item in qs:
            transaction = item.transaction
            seller = transaction.seller
            listing = transaction.listing
            records.append({
                "id": item.id,
                "source": "refund",
                "source_label": "Reservation Refund",
                "amount": item.deposit_amount,
                "payment_status": item.payment_status,
                "payment_reference": item.refund_reference,
                "paid_at": item.paid_at,
                "refunded_at": item.refunded_at,
                "seller_id": seller.id if seller else None,
                "seller_name": getattr(seller, "name", "") if seller else "",
                "seller_email": (
                    (getattr(seller, "email", "") or "") if seller else ""
                ),
                "listing_id": listing.id if listing else None,
                "listing_title": (
                    getattr(listing, "title", "") if listing else ""
                ),
                "status": item.status,
                "created_at": item.created_at,
            })

    records.sort(
        key=lambda r: (
            r["paid_at"] or r["refunded_at"] or r["created_at"]
        ),
        reverse=True,
    )
    return records