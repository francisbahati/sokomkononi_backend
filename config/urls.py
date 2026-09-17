from django.contrib import admin
from django.urls import include, path

from drf_spectacular.views import (
    SpectacularAPIView,
    SpectacularRedocView,
    SpectacularSwaggerView,
)


urlpatterns = [
    path(
        "admin/",
        admin.site.urls,
    ),

    path(
        "api/auth/",
        include("apps.accounts.urls"),
    ),

    path(
        "api/categories/",
        include("apps.categories.urls"),
    ),

    path(
        "api/listings/",
        include("apps.listings.urls"),
    ),

    path(
        "api/schema/",
        SpectacularAPIView.as_view(),
        name="schema",
    ),

    path(
        "api/docs/",
        SpectacularSwaggerView.as_view(
            url_name="schema",
        ),
        name="swagger-ui",
    ),

    path(
        "api/redoc/",
        SpectacularRedocView.as_view(
            url_name="schema",
        ),
        name="redoc",
    ),

    path(
        "api/deals/",
        include("apps.deals.urls"),
    ),

    path(
        "api/transactions/",
        include("apps.transactions.urls"),
    ),

    path(
        "api/waiting-list/",
        include("apps.waiting_list.urls"),
    ),

    path(
        "api/notifications/",
        include("apps.notifications.urls"),
    ),

    path(
        "api/boosting/",
        include("apps.boosting.urls"),
    ),

    path(
        "api/finance/",
        include("apps.finance.urls"),
    ),

    # Soft-delete recycle bin
    path(
        "api/trash/",
        include("apps.core.urls"),
    ),
]