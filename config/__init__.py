"""
Celery bootstrap for SokoMkononi.

Importing the Celery app here ensures @shared_task decorators across
the project register against a single shared instance, and that
`celery -A config worker` and `celery -A config beat` can discover
tasks via autodiscovery.
"""

from .celery import app as celery_app

__all__ = ("celery_app",)