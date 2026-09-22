from django.apps import AppConfig


class AccountsConfig(AppConfig):

    def ready(self):
        from . import schema  # noqa: F401


    default_auto_field = (
        "django.db.models.BigAutoField"
    )

    name = "apps.accounts"

    label = "accounts"

    verbose_name = "Watumiaji"