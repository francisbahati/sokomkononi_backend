# ============================================================
# apps/core/constants.py
#
# AUDIT_PROTECTED_MODEL_NAMES inatumika na:
#   1. tasks.purge_soft_deleted  → inaruka models hizi (bila force)
#   2. trash.views._is_protected → inakataa delete bila force=true
#
# Admin anaweza kufuta kwa `force=true` kupitia trash API,
# au kwa `hard_delete_selected` kwenye Django admin.
# ============================================================

SOFT_DELETE_RETENTION_DAYS = 90

# Models that must NEVER be hard-deleted via the trash API or the
# purge_soft_deleted task. Financial and audit records.
AUDIT_PROTECTED_MODEL_NAMES = {
    # Listings — ina financial records (ListingFee, Boost, Reservation)
    ("listings", "Listing"),
    ("listings", "ListingFee"),
    ("boosting", "ListingBoost"),

    # Transactions / payments
    ("transactions", "Reservation"),
    ("transactions", "InspectionPeriod"),
    ("transactions", "Transaction"),

    # Bundles / banners
    ("bundles", "BundlePurchase"),
    ("banners", "BannerAd"),

    # Auth / audit
    ("accounts", "OTPVerification"),
    ("accounts", "User"),
    ("audit", "AuditLog"),
}