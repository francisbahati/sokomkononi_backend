"""
Print every user with their login-relevant flags.

Usage:
    python manage.py list_users
    python manage.py list_users --unverified
    python manage.py list_users --deleted
"""
from django.core.management.base import BaseCommand

from apps.accounts.models import User


class Command(BaseCommand):
    help = "List users and their state."

    def add_arguments(self, parser):
        parser.add_argument("--unverified", action="store_true")
        parser.add_argument("--deleted", action="store_true")
        parser.add_argument("--inactive", action="store_true")

    def handle(self, *args, **options):
        qs = User.all_objects.all().order_by("-created_at")

        if options["unverified"]:
            qs = qs.filter(is_verified=False)
        if options["deleted"]:
            qs = qs.filter(is_deleted=True)
        if options["inactive"]:
            qs = qs.filter(is_active=False)

        count = qs.count()
        self.stdout.write(f"Total: {count} user(s)")
        self.stdout.write("")
        self.stdout.write(
            f"{'ID':<6}{'Email':<40}{'Active':<8}{'Verified':<10}{'Deleted':<9}"
        )
        self.stdout.write("-" * 75)
        for u in qs[:200]:
            self.stdout.write(
                f"{u.pk:<6}{(u.email or u.deleted_email or '—')[:38]:<40}"
                f"{str(u.is_active):<8}{str(u.is_verified):<10}{str(u.is_deleted):<9}"
            )
        if count > 200:
            self.stdout.write(f"... and {count - 200} more")
