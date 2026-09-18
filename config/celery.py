import os

from celery import Celery


os.environ.setdefault(
    "DJANGO_SETTINGS_MODULE",
    "config.settings",
)


app = Celery("sokomkononi")

# Read config from Django settings, using the CELERY_ namespace.
app.config_from_object(
    "django.conf:settings",
    namespace="CELERY",
)

# Auto-discover tasks.py in every installed app.
app.autodiscover_tasks()


@app.task(ignore_result=True)
def debug_task():
    print("Celery debug task executed.")