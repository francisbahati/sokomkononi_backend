# apps/transactions/management/commands/expire_overdue_payments.py
# (hakikisha folda zina __init__.py: management/ na management/commands/)
from django.core.management.base import BaseCommand

from apps.transactions.services.payment_expiry import expire_overdue_payments


class Command(BaseCommand):
    help = "Ghairi malipo ya mwisho yaliyochelewa na peleka muuzaji kimya kwa admin."

    def handle(self, *args, **options):
        result = expire_overdue_payments()
        self.stdout.write(
            f"cancelled={result['cancelled']} escalated={result['escalated']}"
        )