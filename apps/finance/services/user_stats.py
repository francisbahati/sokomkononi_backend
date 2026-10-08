# apps/finance/services/user_stats.py
"""
User statistics kwa admin dashboard na reports.

Sheria:
- Admin (is_staff=True) HAhesabiwi kama seller/buyer
- Seller = user mwenye Listing angalau moja
- Buyer  = user mwenye DealRoom angalau moja (kama buyer)
- bothRoles = watumiaji ambao ni seller NA buyer
- totalUsers = users wote (is_staff=False, is_deleted=False)

Mtumiaji mmoja anaweza kuwa seller NA buyer kwa wakati mmoja.
"""

from django.contrib.auth import get_user_model
from django.db.models import Q


def calculate_user_stats():
    """
    Rudisha dict yenye:
        - totalUsers
        - totalSellers
        - totalBuyers
        - bothRoles
        - totalAdmins
    """
    User = get_user_model()

    # Users wote (bila admin, bila waliofutwa)
    base_users = User.objects.filter(
        is_staff=False,
        is_deleted=False,
    )
    total_users = base_users.count()

    # Admins pekee
    total_admins = User.objects.filter(
        is_staff=True,
        is_deleted=False,
    ).count()

    # ── SELLERS ──────────────────────────────────────────────
    # Users walio na listing angalau moja (hazijafutwa)
    try:
        from apps.listings.models import Listing

        seller_ids = set(
            Listing.objects
            .filter(
                is_deleted=False,
                seller__is_staff=False,
                seller__is_deleted=False,
            )
            .values_list("seller_id", flat=True)
            .distinct()
        )
    except Exception:
        seller_ids = set()

    # ── BUYERS ───────────────────────────────────────────────
    # Users walio na DealRoom angalau moja kama buyer
    try:
        from apps.deals.models import DealRoom

        buyer_ids = set(
            DealRoom.objects
            .filter(
                buyer__is_staff=False,
                buyer__is_deleted=False,
            )
            .values_list("buyer_id", flat=True)
            .distinct()
        )
    except Exception:
        buyer_ids = set()

    # ── TOTALS ──────────────────────────────────────────────
    total_sellers = len(seller_ids)
    total_buyers = len(buyer_ids)

    # Watumiaji ambao ni seller NA buyer
    both_roles = len(seller_ids & buyer_ids)

    # Watumiaji ambao HAWAJAkuwa seller wala buyer
    neither = total_users - len(seller_ids | buyer_ids)

    return {
        "totalUsers": total_users,
        "totalSellers": total_sellers,
        "totalBuyers": total_buyers,
        "bothRoles": both_roles,
        "neitherRole": max(0, neither),
        "totalAdmins": total_admins,
    }