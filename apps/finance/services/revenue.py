
from datetime import datetime, time, timedelta
from decimal import Decimal

from django.db.models import Sum
from django.utils import timezone

from apps.boosting.models import ListingBoost
from apps.listings.models import ListingFee
from apps.transactions.models import Reservation


ZERO = Decimal("0.00")


def get_period_range(period):
    """
    Return (start, end) for the requested reporting period.

    Supported:
        all
        today
        week
        month
    """

    now = timezone.localtime()

    if period == "today":
        start = datetime.combine(
            now.date(),
            time.min,
            tzinfo=now.tzinfo,
        )
        end = start + timedelta(days=1)

    elif period == "week":
        start_date = (
            now.date()
            - timedelta(days=now.weekday())
        )

        start = datetime.combine(
            start_date,
            time.min,
            tzinfo=now.tzinfo,
        )

        end = start + timedelta(days=7)

    elif period == "month":
        start_date = now.date().replace(day=1)

        start = datetime.combine(
            start_date,
            time.min,
            tzinfo=now.tzinfo,
        )

        if start_date.month == 12:
            next_month = start_date.replace(
                year=start_date.year + 1,
                month=1,
                day=1,
            )
        else:
            next_month = start_date.replace(
                month=start_date.month + 1,
                day=1,
            )

        end = datetime.combine(
            next_month,
            time.min,
            tzinfo=now.tzinfo,
        )

    elif period == "all":
        return None, None

    else:
        raise ValueError(
            "Invalid period. Use: all, today, week, or month."
        )

    return start, end


def _apply_date_filter(queryset, start, end, field="created_at"):
    if start is None or end is None:
        return queryset

    return queryset.filter(
        **{
            f"{field}__gte": start,
            f"{field}__lt": end,
        }
    )


def calculate_financial_dashboard(period="all"):
    start, end = get_period_range(period)

    # Listing Fees
    listing_fees = ListingFee.objects.filter(
        payment_status="PAID"
    )

    listing_fees = _apply_date_filter(
        listing_fees,
        start,
        end,
        field="paid_at",
    )

    listing_fee_revenue = (
        listing_fees.aggregate(
            total=Sum("amount")
        )["total"]
        or ZERO
    )

    paid_listing_fees = listing_fees.count()

    # Reservations
    reservations = Reservation.objects.filter(
        payment_status="PAID"
    )

    reservations = _apply_date_filter(
        reservations,
        start,
        end,
        field="paid_at",
    )

    reservation_revenue = (
        reservations.aggregate(
            total=Sum("deposit_amount")
        )["total"]
        or ZERO
    )

    paid_reservations = reservations.count()

    # Boosting
    boosts = ListingBoost.objects.filter(
        payment_status="PAID"
    )

    boosts = _apply_date_filter(
        boosts,
        start,
        end,
        field="paid_at",
    )

    boosting_revenue = (
        boosts.aggregate(
            total=Sum("amount")
        )["total"]
        or ZERO
    )

    paid_boosts = boosts.count()

    # Refunds
    refunds = Reservation.objects.filter(
        payment_status="REFUNDED"
    )

    refunds = _apply_date_filter(
        refunds,
        start,
        end,
        field="refunded_at",
    )

    refund_amount = (
        refunds.aggregate(
            total=Sum("deposit_amount")
        )["total"]
        or ZERO
    )

    refund_count = refunds.count()

    # Future revenue sources
    advertisement_revenue = ZERO
    leading_revenue = ZERO

    # Totals
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


def get_revenue_records(
    period="all",
    source="all",
):
    """
    Return individual financial records.

    Supported sources:
        all
        listing_fee
        reservation
        boosting
        refund
    """

    start, end = get_period_range(period)

    records = []

    # Listing Fees
    if source in {"all", "listing_fee"}:
        queryset = ListingFee.objects.filter(
            payment_status="PAID"
        ).select_related(
            "seller",
            "listing",
        )

        queryset = _apply_date_filter(
            queryset,
            start,
            end,
            field="paid_at",
        )

        for item in queryset:
            records.append(
                {
                    "id": item.id,
                    "source": "listing_fee",
                    "source_label": "Listing Fee",
                    "amount": item.amount,
                    "payment_status": item.payment_status,
                    "payment_reference": item.payment_reference,
                    "paid_at": item.paid_at,
                    "refunded_at": None,
                    "seller_id": item.seller_id,
                    "seller_name": getattr(
                        item.seller,
                        "name",
                        "",
                    ),
                    "seller_email": getattr(
                        item.seller,
                        "email",
                        "",
                    ),
                    "listing_id": item.listing_id,
                    "listing_title": getattr(
                        item.listing,
                        "title",
                        "",
                    ),
                    "status": None,
                    "created_at": item.created_at,
                }
            )

    # Reservation Payments
    if source in {"all", "reservation"}:
        queryset = Reservation.objects.filter(
            payment_status="PAID"
        ).select_related(
            "transaction",
            "transaction__seller",
            "transaction__listing",
        )

        queryset = _apply_date_filter(
            queryset,
            start,
            end,
            field="paid_at",
        )

        for item in queryset:
            transaction = item.transaction
            seller = transaction.seller
            listing = transaction.listing

            records.append(
                {
                    "id": item.id,
                    "source": "reservation",
                    "source_label": "Reservation Deposit",
                    "amount": item.deposit_amount,
                    "payment_status": item.payment_status,
                    "payment_reference": item.payment_reference,
                    "paid_at": item.paid_at,
                    "refunded_at": None,
                    "seller_id": seller.id if seller else None,
                    "seller_name": (
                        getattr(seller, "name", "")
                        if seller
                        else ""
                    ),
                    "seller_email": (
                        getattr(seller, "email", "")
                        if seller
                        else ""
                    ),
                    "listing_id": (
                        listing.id
                        if listing
                        else None
                    ),
                    "listing_title": (
                        getattr(listing, "title", "")
                        if listing
                        else ""
                    ),
                    "status": item.status,
                    "created_at": item.created_at,
                }
            )

    # Boosting Payments
    if source in {"all", "boosting"}:
        queryset = ListingBoost.objects.filter(
            payment_status="PAID"
        ).select_related(
            "seller",
            "listing",
            "package",
        )

        queryset = _apply_date_filter(
            queryset,
            start,
            end,
            field="paid_at",
        )

        for item in queryset:
            records.append(
                {
                    "id": item.id,
                    "source": "boosting",
                    "source_label": "Boosting Fee",
                    "amount": item.amount,
                    "payment_status": item.payment_status,
                    "payment_reference": item.payment_reference,
                    "paid_at": item.paid_at,
                    "refunded_at": None,
                    "seller_id": item.seller_id,
                    "seller_name": getattr(
                        item.seller,
                        "name",
                        "",
                    ),
                    "seller_email": getattr(
                        item.seller,
                        "email",
                        "",
                    ),
                    "listing_id": item.listing_id,
                    "listing_title": getattr(
                        item.listing,
                        "title",
                        "",
                    ),
                    "status": item.status,
                    "created_at": item.created_at,
                }
            )

    # Refunds
    if source in {"all", "refund"}:
        queryset = Reservation.objects.filter(
            payment_status="REFUNDED"
        ).select_related(
            "transaction",
            "transaction__seller",
            "transaction__listing",
        )

        queryset = _apply_date_filter(
            queryset,
            start,
            end,
            field="refunded_at",
        )

        for item in queryset:
            transaction = item.transaction
            seller = transaction.seller
            listing = transaction.listing

            records.append(
                {
                    "id": item.id,
                    "source": "refund",
                    "source_label": "Reservation Refund",
                    "amount": item.deposit_amount,
                    "payment_status": item.payment_status,
                    "payment_reference": item.refund_reference,
                    "paid_at": item.paid_at,
                    "refunded_at": item.refunded_at,
                    "seller_id": seller.id if seller else None,
                    "seller_name": (
                        getattr(seller, "name", "")
                        if seller
                        else ""
                    ),
                    "seller_email": (
                        getattr(seller, "email", "")
                        if seller
                        else ""
                    ),
                    "listing_id": (
                        listing.id
                        if listing
                        else None
                    ),
                    "listing_title": (
                        getattr(listing, "title", "")
                        if listing
                        else ""
                    ),
                    "status": item.status,
                    "created_at": item.created_at,
                }
            )

    # Newest first
    records.sort(
        key=lambda record: (
            record["paid_at"]
            or record["refunded_at"]
            or record["created_at"]
        ),
        reverse=True,
    )

    return records
