"""
Mark existing users as verified so they can log in.

Useful when users registered before the OTP flow worked and are now
stuck with is_verified=False.

Usage:
    python manage.py force_verify                     # all unverified
    python manage.py force_verify user@example.com    # one email
"""
from django.core.management.base import BaseCommand

from apps.accounts.models import User


class Command(BaseCommand):
    help = "Force is_verified=True on unverified users."

    def add_arguments(self, parser):
        parser.add_argument(
            "email", nargs="?", default=None,
            help="Optional: only verify this email.",
        )

    def handle(self, *args, **options):
        email = options.get("email")

        qs = User.all_objects.filter(is_verified=False)
        if email:
            qs = qs.filter(email__iexact=email)

        count = qs.count()
        if count == 0:
            self.stdout.write("No unverified users found.")
            return

        self.stdout.write(f"Will verify {count} user(s):")
        for u in qs[:20]:
            self.stdout.write(f"  - {u.pk}  {u.email}")
        if count > 20:
            self.stdout.write(f"  ... and {count - 20} more")

        qs.update(is_verified=True)
        self.stdout.write(self.style.SUCCESS(f"✓ Verified {count} user(s)"))
