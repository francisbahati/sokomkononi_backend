# ============================================================
# apps/core/constants.py
#
# Marekebisho:
#  - Ongeza ("listings", "Listing") kwenye AUDIT_PROTECTED_MODEL_NAMES
#    ili Listing isifutwe kabisa (ina financial records).
# ============================================================

SOFT_DELETE_RETENTION_DAYS = 90

# Models that must NEVER be hard-deleted via the trash API or the
# purge_soft_deleted task. Financial and audit records.
AUDIT_PROTECTED_MODEL_NAMES = {
    # Listings — ina financial records (ListingFee, Boost, Reservation)
    ("listings", "Listing"),          # ⬅️ MPYA
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