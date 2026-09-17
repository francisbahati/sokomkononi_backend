from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin

from apps.core.admin import SoftDeleteAdminMixin

from .models import (
    OTPVerification,
    PendingRegistration,
    User,
)


@admin.register(User)
class UserAdmin(SoftDeleteAdminMixin, BaseUserAdmin):

    ordering = ["-created_at"]

    list_display = [
        "id",
        "name",
        "email",
        "phone",
        "account_type",
        "is_verified",
        "is_active",
        "is_staff",
        "is_deleted",
        "created_at",
    ]

    list_filter = [
        "account_type",
        "is_verified",
        "is_active",
        "is_staff",
        "created_at",
    ]

    search_fields = [
        "name",
        "email",
        "phone",
    ]

    readonly_fields = [
        "created_at",
        "updated_at",
        "last_login",
        "date_joined",
        "deleted_at",
        "deleted_by",
    ]

    fieldsets = (
        (
            "Taarifa za Akaunti",
            {
                "fields": (
                    "email",
                    "phone",
                    "password",
                )
            },
        ),
        (
            "Taarifa Binafsi",
            {
                "fields": (
                    "name",
                    "account_type",
                )
            },
        ),
        (
            "Uthibitishaji",
            {
                "fields": (
                    "is_verified",
                )
            },
        ),
        (
            "Ruhusa",
            {
                "fields": (
                    "is_active",
                    "is_staff",
                    "is_superuser",
                    "groups",
                    "user_permissions",
                )
            },
        ),
        (
            "Tarehe",
            {
                "fields": (
                    "last_login",
                    "date_joined",
                    "created_at",
                    "updated_at",
                )
            },
        ),
        (
            "Kikapu",
            {
                "fields": (
                    "is_deleted",
                    "deleted_at",
                    "deleted_by",
                    "deletion_reason",
                )
            },
        ),
    )

    add_fieldsets = (
        (
            "Unda Mtumiaji",
            {
                "classes": (
                    "wide",
                ),
                "fields": (
                    "email",
                    "name",
                    "phone",
                    "password1",
                    "password2",
                    "account_type",
                    "is_verified",
                    "is_active",
                    "is_staff",
                ),
            },
        ),
    )


@admin.register(PendingRegistration)
class PendingRegistrationAdmin(
    admin.ModelAdmin
):

    list_display = [
        "id",
        "name",
        "email",
        "phone",
        "account_type",
        "created_at",
        "updated_at",
    ]

    list_filter = [
        "account_type",
        "created_at",
    ]

    search_fields = [
        "name",
        "email",
        "phone",
    ]

    readonly_fields = [
        "password_hash",
        "created_at",
        "updated_at",
    ]


@admin.register(OTPVerification)
class OTPVerificationAdmin(
    admin.ModelAdmin
):

    list_display = [
        "id",
        "identifier",
        "verification_type",
        "is_used",
        "attempts",
        "created_at",
        "expires_at",
        "verified_at",
    ]

    list_filter = [
        "verification_type",
        "is_used",
        "created_at",
    ]

    search_fields = [
        "identifier",
    ]

    readonly_fields = [
        "otp_code",
        "created_at",
        "expires_at",
        "verified_at",
    ]