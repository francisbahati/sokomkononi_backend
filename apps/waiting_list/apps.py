from django.apps import AppConfig


class WaitingListConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.waiting_list"
    label = "waiting_list"
    verbose_name = "Waiting List"