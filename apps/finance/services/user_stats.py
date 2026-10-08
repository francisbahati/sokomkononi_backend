# apps/finance/services/user_stats.py
"""
User statistics kwa admin dashboard na reports.

Sheria:
- Admin (is_staff=True) HAhesabiwi kama seller/buyer
- Seller = user mwenye Listing angalau moja
- Buyer  = user mwenye DealRoom angalau moja (kama buyer)
- bothRoles = watumiaji ambao ni seller NA buyer
- sellersOnly = sellers ambao SIO buyers
- buyersOnly  = buyers ambao SIO sellers
- neitherRole = hawana listing wala deal
- totalUsers = users wote (is_staff=False, is_deleted=False)

Mtumiaji mmoja anaweza kuwa seller NA buyer kwa wakati mmoja.
"""

from django.contrib.auth import get_user_model


def calculate_user_stats():
    """
    Rudisha dict yenye:
        - totalUsers
        - totalSellers
        - totalBuyers
        - sellersOnly
        - buyersOnly
        - bothRoles
        - neitherRole
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

    # ── BREAKDOWN ───────────────────────────────────────────
    both_roles = seller_ids & buyer_ids
    sellers_only = seller_ids - buyer_ids
    buyers_only = buyer_ids - seller_ids
    neither = (
        set(base_users.values_list("id", flat=True))
        - (seller_ids | buyer_ids)
    )

    return {
        "totalUsers": total_users,
        "totalSellers": len(seller_ids),
        "totalBuyers": len(buyer_ids),
        "sellersOnly": len(sellers_only),
        "buyersOnly": len(buyers_only),
        "bothRoles": len(both_roles),
        "neitherRole": max(0, len(neither)),
        "totalAdmins": total_admins,
    }