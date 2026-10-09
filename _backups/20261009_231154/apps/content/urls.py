"""Public content routes — reads only. Writes live in urls_admin.py."""
from django.urls import path

from .views import ContentViewSet
from .views_admin import AdminContentViewSet


urlpatterns = [
    path(
        "",
        ContentViewSet.as_view({"get": "list"}),
        name="content-list",
    ),
    path(
        "about/",
        ContentViewSet.as_view({"get": "by_key"}),
        {"key": "about"},
        name="content-about",
    ),
    path(
        "terms/",
        ContentViewSet.as_view({"get": "by_key"}),
        {"key": "terms"},
        name="content-terms",
    ),
    path(
        "privacy/",
        ContentViewSet.as_view({"get": "by_key"}),
        {"key": "privacy"},
        name="content-privacy",
    ),
    path(
        "help/",
        ContentViewSet.as_view({"get": "by_key"}),
        {"key": "help"},
        name="content-help",
    ),

    # Public reads for banners / testimonials / faqs
    path(
        "banners/",
        AdminContentViewSet.as_view({"get": "list_content"}),
        {"kind": "banners"},
        name="content-banners",
    ),
    path(
        "banners/<int:pk>/",
        AdminContentViewSet.as_view({"get": "detail_content"}),
        {"kind": "banners"},
        name="content-banner-detail",
    ),
    path(
        "testimonials/",
        AdminContentViewSet.as_view({"get": "list_content"}),
        {"kind": "testimonials"},
        name="content-testimonials",
    ),
    path(
        "testimonials/<int:pk>/",
        AdminContentViewSet.as_view({"get": "detail_content"}),
        {"kind": "testimonials"},
        name="content-testimonial-detail",
    ),
    path(
        "faqs/",
        AdminContentViewSet.as_view({"get": "list_content"}),
        {"kind": "faqs"},
        name="content-faqs",
    ),
    path(
        "faqs/<int:pk>/",
        AdminContentViewSet.as_view({"get": "detail_content"}),
        {"kind": "faqs"},
        name="content-faq-detail",
    ),
]
