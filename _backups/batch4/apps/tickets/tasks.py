# apps/tickets/tasks.py
"""
SLA reminders kwa tickets.

Task hii inaitwa na Celery Beat kila saa 1:
  - Tafuta tickets ambazo SLA deadline imepita
  - Hazijatatuliwa (status = OPEN au IN_PROGRESS)
  - Hazijakumbushwa bado (sla_reminded_at ni null)
  - Tuma notification kwa admin wote
  - Weka sla_reminded_at = now
"""
import logging

from celery import shared_task
from django.utils import timezone

from apps.notifications.models import Notification
from apps.notifications.services.notification import create_notification_for_admins

from .models import Ticket

logger = logging.getLogger(__name__)


@shared_task(name="tickets.send_sla_reminders")
def send_sla_reminders():
    """
    Tafuta tickets zilizopita SLA na hazijatatuliwa,
    tuma notification kwa admin.
    """
    now = timezone.now()

    overdue = (
        Ticket.objects
        .filter(
            sla_deadline__lt=now,
            sla_reminded_at__isnull=True,
        )
        .exclude(
            status__in=[
                Ticket.Status.RESOLVED,
                Ticket.Status.CLOSED,
            ]
        )
        .select_related("user", "assigned_to")
    )

    count = 0
    for ticket in overdue:
        try:
            create_notification_for_admins(
                notification_type=Notification.NotificationType.GENERAL,
                title=f"SLA imepita: {ticket.code}",
                message=(
                    f"Ticket \"{ticket.subject}\" haijajibiwa kwa saa 24+. "
                    f"Priority: {ticket.priority}. "
                    f"Kutoka: {ticket.user_name or ticket.user_email}."
                ),
                priority=Notification.Priority.URGENT,
                related_object_type="ticket",
                related_object_id=ticket.id,
                action_url=f"/smk-control-9x7k/support?ticket={ticket.id}",
            )
            ticket.sla_reminded_at = now
            ticket.save(update_fields=["sla_reminded_at"])
            count += 1
        except Exception:
            logger.exception("SLA reminder failed for ticket %s", ticket.id)

    logger.info("[tickets.sla] sent %s SLA reminders", count)
    return {"sent": count}