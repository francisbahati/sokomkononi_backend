from django.urls import path

from .views_admin import AdminContentViewSet


def _dispatch(request, kind, pk=None):
    view = AdminContentViewSet.as_view({"get": "list_content", "post": "create_content"})
    return view(request, kind=kind)


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