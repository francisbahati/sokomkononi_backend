from django.urls import path

from .views_admin import AdminContentViewSet


def _dispatch(request, kind, pk=None):
    view = AdminContentViewSet.as_view({"get": "list", "post": "create"})
    return view(request, kind=kind)


urlpatterns = [
    # Banners
    path(
        "banners/",
        AdminContentViewSet.as_view({"get": "_list", "post": "_create"}),
        {"kind": "banners"},
        name="admin-banners",
    ),
    path(
        "banners/<int:pk>/",
        AdminContentViewSet.as_view({
            "get": "_detail",
            "patch": "_detail",
            "delete": "_detail",
        }),
        {"kind": "banners"},
        name="admin-banner-detail",
    ),

    # Testimonials
    path(
        "testimonials/",
        AdminContentViewSet.as_view({"get": "_list", "post": "_create"}),
        {"kind": "testimonials"},
        name="admin-testimonials",
    ),
    path(
        "testimonials/<int:pk>/",
        AdminContentViewSet.as_view({
            "get": "_detail",
            "patch": "_detail",
            "delete": "_detail",
        }),
        {"kind": "testimonials"},
        name="admin-testimonial-detail",
    ),

    # FAQs
    path(
        "faqs/",
        AdminContentViewSet.as_view({"get": "_list", "post": "_create"}),
        {"kind": "faqs"},
        name="admin-faqs",
    ),
    path(
        "faqs/<int:pk>/",
        AdminContentViewSet.as_view({
            "get": "_detail",
            "patch": "_detail",
            "delete": "_detail",
        }),
        {"kind": "faqs"},
        name="admin-faq-detail",
    ),
]