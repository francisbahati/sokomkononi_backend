# ============================================================
# config/urls.py
# ============================================================

from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import include, path

from drf_spectacular.views import (
    SpectacularAPIView,
    SpectacularSwaggerView,
)


urlpatterns = [
    # Admin
    path("admin/", admin.site.urls),

    # Schema / docs
    path("api/schema/", SpectacularAPIView.as_view(), name="schema"),
    path(
        "api/docs/",
        SpectacularSwaggerView.as_view(url_name="schema"),
        name="docs",
    ),

    # Apps
    path("api/auth/", include("apps.accounts.urls")),
    path("api/categories/", include("apps.categories.urls")),
    path("api/listings/", include("apps.listings.urls")),
    path("api/boosting/", include("apps.boosting.urls")),
    path("api/deals/", include("apps.deals.urls")),
    path("api/transactions/", include("apps.transactions.urls")),
    path("api/finance/", include("apps.finance.urls")),
    path("api/notifications/", include("apps.notifications.urls")),
    path("api/trash/", include("apps.core.urls")),
]


if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)