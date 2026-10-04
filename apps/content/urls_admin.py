from django.urls import path

from .views_admin import AdminContentViewSet, AdminSiteContentView


urlpatterns = [
    # Banners
    path(
        "banners/",
        AdminContentViewSet.as_view({"get": "list_content", "post": "create_content"}),
        {"kind": "banners"},
        name="admin-banners",
    ),
    path(
        "banners/<int:pk>/",
        AdminContentViewSet.as_view({
            "get": "detail_content",
            "patch": "detail_content",
            "delete": "detail_content",
        }),
        {"kind": "banners"},
        name="admin-banner-detail",
    ),

    # Testimonials
    path(
        "testimonials/",
        AdminContentViewSet.as_view({"get": "list_content", "post": "create_content"}),
        {"kind": "testimonials"},
        name="admin-testimonials",
    ),
    path(
        "testimonials/<int:pk>/",
        AdminContentViewSet.as_view({
            "get": "detail_content",
            "patch": "detail_content",
            "delete": "detail_content",
        }),
        {"kind": "testimonials"},
        name="admin-testimonial-detail",
    ),

    # Site content: about / terms / privacy / help
    path(
        "about/",
        AdminSiteContentView.as_view({"get": "retrieve", "patch": "partial_update"}),
        {"key": "about"}, name="admin-content-about",
    ),
    path(
        "terms/",
        AdminSiteContentView.as_view({"get": "retrieve", "patch": "partial_update"}),
        {"key": "terms"}, name="admin-content-terms",
    ),
    path(
        "privacy/",
        AdminSiteContentView.as_view({"get": "retrieve", "patch": "partial_update"}),
        {"key": "privacy"}, name="admin-content-privacy",
    ),
    path(
        "help/",
        AdminSiteContentView.as_view({"get": "retrieve", "patch": "partial_update"}),
        {"key": "help"}, name="admin-content-help",
    ),

    # FAQs
    path(
        "faqs/",
        AdminContentViewSet.as_view({"get": "list_content", "post": "create_content"}),
        {"kind": "faqs"},
        name="admin-faqs",
    ),
    path(
        "faqs/<int:pk>/",
        AdminContentViewSet.as_view({
            "get": "detail_content",
            "patch": "detail_content",
            "delete": "detail_content",
        }),
        {"kind": "faqs"},
        name="admin-faq-detail",
    ),
]
