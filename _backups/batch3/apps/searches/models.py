from django.conf import settings
from django.db import models


class SavedSearch(models.Model):
    """
    A buyer's saved search with alert criteria. Matches are computed
    against listings by the alert Celery task.
    """

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="saved_searches",
        verbose_name="Mtumiaji",
    )

    name = models.CharField(
        max_length=150,
        verbose_name="Jina la utafutaji",
    )

    query = models.CharField(
        max_length=255,
        blank=True,
        verbose_name="Neno la utafutaji",
    )

    category_slug = models.CharField(
        max_length=120,
        blank=True,
        verbose_name="Slug ya kundi",
    )

    region = models.CharField(
        max_length=100,
        blank=True,
        verbose_name="Mkoa",
    )

    min_price = models.DecimalField(
        max_digits=15,
        decimal_places=2,
        null=True,
        blank=True,
        verbose_name="Bei ya chini",
    )

    max_price = models.DecimalField(
        max_digits=15,
        decimal_places=2,
        null=True,
        blank=True,
        verbose_name="Bei ya juu",
    )

    verified_only = models.BooleanField(
        default=False,
        verbose_name="Zilizothibitishwa pekee",
    )

    match_count = models.PositiveIntegerField(
        default=0,
        verbose_name="Idadi ya match",
    )

    last_checked = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name="Ilipokaguliwa mwisho",
    )

    created_at = models.DateTimeField(
        auto_now_add=True,
        verbose_name="Imeundwa",
    )

    class Meta:
        db_table = "saved_searches"
        ordering = ["-created_at"]
        verbose_name = "Utafutaji uliosajiliwa"
        verbose_name_plural = "Utafutaji uliosajiliwa"

        indexes = [
            models.Index(
                fields=["user", "created_at"],
                name="ssearch_user_time_idx",
            ),
        ]

    def __str__(self):
        return f"{self.user} — {self.name}"


class SavedSearchMatch(models.Model):
    """
    Dedup table: records which listings have already triggered an alert
    for a given search, so we don't spam the user.
    """

    search = models.ForeignKey(
        SavedSearch,
        on_delete=models.CASCADE,
        related_name="matches",
    )
    listing = models.ForeignKey(
        "listings.Listing",
        on_delete=models.CASCADE,
        related_name="search_matches",
    )
    notified_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "saved_search_matches"
        ordering = ["-notified_at"]
        constraints = [
            models.UniqueConstraint(
                fields=["search", "listing"],
                name="unique_search_listing_match",
            ),
        ]

    def __str__(self):
        return f"{self.search.name} → {self.listing.title}"