# apps/finance/services/overview_stats.py
"""
Takwimu za Overview ya admin, zote kwa request moja (hakuna cache ya
frontend, kwa hiyo hakuna "flash" ya namba za zamani).
"""
from django.db.models import Count, Q

from .user_stats import calculate_user_stats

DRAFT_STATUSES = ["DRAFT", "PENDING_PAYMENT"]
PENDING_REVIEW_STATUSES = ["PENDING_APPROVAL", "PAID_PENDING_APPROVAL"]

ACTIVE_DEAL_STATUSES = [
    "OPEN", "NEGOTIATING", "ACCEPTED", "RESERVED",
    "AWAITING_FINAL_PAYMENT", "PAYMENT_PROOF_SUBMITTED",
]


def calculate_overview_stats():
    from apps.deals.models import DealRoom
    from apps.listings.models import Listing, ListingFee
    from apps.transactions.models import Reservation

    from ..models import SuccessFeePayment

    listings = Listing.objects.filter(is_deleted=False).aggregate(
        total=Count("id"),
        drafts=Count("id", filter=Q(status__in=DRAFT_STATUSES)),
        pending=Count("id", filter=Q(status__in=PENDING_REVIEW_STATUSES)),
    )

    deals = DealRoom.objects.aggregate(
        active=Count("id", filter=Q(status__in=ACTIVE_DEAL_STATUSES)),
        completed=Count("id", filter=Q(status="COMPLETED")),
    )

    # Malipo yaliyoanzishwa lakini bado hayajathibitishwa (jukwaa zima)
    pending_payments = (
        ListingFee.objects.filter(payment_status="PENDING").count()
        + Reservation.objects.filter(payment_status="PENDING").count()
        + SuccessFeePayment.objects.filter(payment_status="PENDING").count()
    )

    return {
        "users": calculate_user_stats(),
        "listings": listings,
        "deals": deals,
        "pendingPayments": pending_payments,
    }
