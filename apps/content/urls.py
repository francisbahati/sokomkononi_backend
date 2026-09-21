from django.urls import path

from .views import ContentViewSet
from .views_admin import AdminContentViewSet


urlpatterns = [
    # Root content
    path("", ContentViewSet.as_view({"get": "list"}), name="content-list"),

    # Banners
    path(
        "banners/",
        AdminContentViewSet.as_view({"get": "_list", "post": "_create"}),
        {"kind": "banners"},
        name="content-banners",
    ),
    path(
        "banners/<int:pk>/",
        AdminContentViewSet.as_view({
            "get": "_detail", "patch": "_detail", "delete": "_detail",
        }),
        {"kind": "banners"},
        name="content-banner-detail",
    ),

    # Testimonials
    path(
        "testimonials/",
        AdminContentViewSet.as_view({"get": "_list", "post": "_create"}),
        {"kind": "testimonials"},
        name="content-testimonials",
    ),
    path(
        "testimonials/<int:pk>/",
        AdminContentViewSet.as_view({
            "get": "_detail", "patch": "_detail", "delete": "_detail",
        }),
        {"kind": "testimonials"},
        name="content-testimonial-detail",
    ),

    # FAQs
    path(
        "faqs/",
        AdminContentViewSet.as_view({"get": "_list", "post": "_create"}),
        {"kind": "faqs"},
        name="content-faqs",
    ),
    path(
        "faqs/<int:pk>/",
        AdminContentViewSet.as_view({
            "get": "_detail", "patch": "_detail", "delete": "_detail",
        }),
        {"kind": "faqs"},
        name="content-faq-detail",
    ),

    # Section content (about/terms/privacy/help)
    path(
        "about/",
        ContentViewSet.as_view({"get": "by_key", "patch": "update_key"}),
        {"key": "about"},
        name="content-about",
    ),
    path(
        "terms/",
        ContentViewSet.as_view({"get": "by_key", "patch": "update_key"}),
        {"key": "terms"},
        name="content-terms",
    ),
    path(
        "privacy/",
        ContentViewSet.as_view({"get": "by_key", "patch": "update_key"}),
        {"key": "privacy"},
        name="content-privacy",
    ),
    path(
        "help/",
        ContentViewSet.as_view({"get": "by_key", "patch": "update_key"}),
        {"key": "help"},
        name="content-help",
    ),
]
