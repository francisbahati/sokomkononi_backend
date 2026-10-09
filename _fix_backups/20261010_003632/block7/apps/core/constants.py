SOFT_DELETE_RETENTION_DAYS = 90

# Models that must NEVER be hard-deleted via the trash API or the
# purge_soft_deleted task. Financial and audit records.
AUDIT_PROTECTED_MODEL_NAMES = {
    ("listings", "ListingFee"),
    ("boosting", "ListingBoost"),
    ("transactions", "Reservation"),
    ("transactions", "InspectionPeriod"),
    ("transactions", "Transaction"),
    ("accounts", "OTPVerification"),
    ("bundles", "BundlePurchase"),
    ("banners", "BannerAd"),
    ("audit", "AuditLog"),
    ("accounts", "User"),
}
