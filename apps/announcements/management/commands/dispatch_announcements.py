# apps/announcements/management/commands/dispatch_announcements.py   (FILE MPYA)
#
# Mbadala wa Celery beat: ita kila dakika kupitia cron.
#   * * * * *  cd /path/to/project && python manage.py dispatch_announcements
from django.core.management.base import BaseCommand

from apps.announcements.services import dispatch_pending


class Command(BaseCommand):
    help = "Tuma arifa za matangazo yaliyofikia muda wake (ratiba)."

    def handle(self, *args, **options):
        results = dispatch_pending()
        sent = sum(1 for r in results.values() if r.get("status") == "sent")
        self.stdout.write(f"announcements dispatched: {sent}/{len(results)}")
