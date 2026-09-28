from django.urls import path

from .views import ContentViewSet
from .views_admin import AdminContentViewSet


urlpatterns = [
    # Root content (aggregated) — ContentViewSet.list
    path(
        "",
        ContentViewSet.as_view({"get": "list"}),
        name="content-list",
    ),

    # Banners
    path(
        "banners/",
        AdminContentViewSet.as_view({"get": "list_content", "post": "create_content"}),
        {"kind": "banners"},
        name="content-banners",
    ),
    path(
        "banners/<int:pk>/",
        AdminContentViewSet.as_view({
            "get": "detail_content",
            "patch": "detail_content",
            "delete": "detail_content",
        }),
        {"kind": "banners"},
        name="content-banner-detail",
    ),

    # Testimonials
    path(
        "testimonials/",
        AdminContentViewSet.as_view({"get": "list_content", "post": "create_content"}),
        {"kind": "testimonials"},
        name="content-testimonials",
    ),
    path(
        "testimonials/<int:pk>/",
        AdminContentViewSet.as_view({
            "get": "detail_content",
            "patch": "detail_content",
            "delete": "detail_content",
        }),
        {"kind": "testimonials"},
        name="content-testimonial-detail",
    ),

    # FAQs
    path(
        "faqs/",
        AdminContentViewSet.as_view({"get": "list_content", "post": "create_content"}),
        {"kind": "faqs"},
        name="content-faqs",
    ),
    path(
        "faqs/<int:pk>/",
        AdminContentViewSet.as_view({
            "get": "detail_content",
            "patch": "detail_content",
            "delete": "detail_content",
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
