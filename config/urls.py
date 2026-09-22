from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import include, path

from drf_spectacular.views import (
    SpectacularAPIView,
    SpectacularSwaggerView,
)


urlpatterns = [
    path("admin/", admin.site.urls),

    # Schema / docs
    path("api/schema/", SpectacularAPIView.as_view(), name="schema"),
    path(
        "api/docs/",
        SpectacularSwaggerView.as_view(url_name="schema"),
        name="docs",
    ),

    # Auth & apps
    path("api/auth/", include("apps.accounts.urls")),
    path("api/contact/", include("apps.contact.urls")),
    path("api/categories/", include("apps.categories.urls")),
    path("api/listings/", include("apps.listings.urls")),
    path(
        "api/admin/listings/",
        include("apps.listings.urls_admin_moderation"),
    ),
    path("api/boosting/", include("apps.boosting.urls")),
    path("api/deals/", include("apps.deals.urls")),
    path("api/transactions/", include("apps.transactions.urls")),
    path("api/finance/", include("apps.finance.urls")),
    path("api/notifications/", include("apps.notifications.urls")),
    path("api/waiting-list/", include("apps.waiting_list.urls")),
    path("api/saved/", include("apps.saved.urls")),
    path("api/searches/", include("apps.searches.urls")),
    path("api/leads/", include("apps.leads.urls")),
    path("api/messaging/", include("apps.messaging.urls")),
    path("api/verifications/", include("apps.verifications.urls")),
    path("api/tickets/", include("apps.tickets.urls")),
    path("api/audit/", include("apps.audit.urls")),
    path("api/announcements/", include("apps.announcements.urls")),
    path("api/content/", include("apps.content.urls")),
    path("api/rbac/", include("apps.rbac.urls")),
    path("api/system-settings/", include("apps.system_settings.urls")),

    # Admin routes
    path("api/admin/users/", include("apps.accounts.urls_admin")),
    path("api/admin/content/", include("apps.content.urls_admin")),
    path(
        "api/admin/reports/",
        include("apps.finance.urls_admin_reports"),
    ),

    # Commerce
    path("api/bundles/", include("apps.bundles.urls")),
    path("api/credits/", include("apps.credits.urls")),
    path("api/banners/", include("apps.banners.urls")),
    path("api/promotions/", include("apps.banners.urls_promotions")),
    path("api/leading-fees/", include("apps.leading_fees.urls")),
    path("api/advertisement-fees/", include("apps.advertisement_fees.urls")),
    path("api/reservation-rates/", include("apps.reservation_rates.urls")),
    path("api/trash/", include("apps.core.urls")),
]


if settings.DEBUG:
    urlpatterns += static(
        settings.MEDIA_URL,
        document_root=settings.MEDIA_ROOT,
    )
    urlpatterns += static(
        settings.STATIC_URL,
        document_root=settings.STATIC_ROOT,
    )
