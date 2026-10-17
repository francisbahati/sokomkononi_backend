from django.contrib import admin

from .models import Banner, FAQ, SiteContent, Testimonial


@admin.register(SiteContent)
class SiteContentAdmin(admin.ModelAdmin):
    list_display = ("key", "heading_sw", "heading_en", "updated_at")
    ordering = ("key",)


@admin.register(Banner)
class BannerAdmin(admin.ModelAdmin):
    list_display = ("id", "title_sw", "active", "order", "created_at")
    list_filter = ("active",)
    ordering = ("order", "id")


@admin.register(Testimonial)
class TestimonialAdmin(admin.ModelAdmin):
    list_display = ("id", "name", "rating", "active", "created_at")
    list_filter = ("active", "rating")
    ordering = ("-created_at",)


@admin.register(FAQ)
class FAQAdmin(admin.ModelAdmin):
    list_display = ("id", "question_sw", "active", "order", "created_at")
    list_filter = ("active",)
    ordering = ("order", "id")