"""
Inspect a user account for login-blocking conditions.

Usage:
    python manage.py inspect_user user@example.com
"""
from django.core.management.base import BaseCommand

from apps.accounts.models import User


class Command(BaseCommand):
    help = "Show login-relevant state for a user."

    def add_arguments(self, parser):
        parser.add_argument("email", type=str)

    def handle(self, *args, **options):
        email = options["email"].strip().lower()

        user = User.all_objects.filter(email__iexact=email).first()
        if not user:
            self.stdout.write(self.style.ERROR(
                f"No user found with email {email!r} (including soft-deleted)."
            ))
            return

        self.stdout.write("============================================")
        self.stdout.write(f" Inspect {user.email}")
        self.stdout.write("============================================")
        self.stdout.write(f"id              : {user.pk}")
        self.stdout.write(f"name            : {user.name}")
        self.stdout.write(f"email           : {user.email}")
        self.stdout.write(f"phone           : {user.phone}")
        self.stdout.write(f"account_type    : {user.account_type}")
        self.stdout.write(f"is_active       : {user.is_active}")
        self.stdout.write(f"is_verified     : {user.is_verified}")
        self.stdout.write(f"is_staff        : {user.is_staff}")
        self.stdout.write(f"is_superuser    : {user.is_superuser}")
        self.stdout.write(f"is_deleted      : {user.is_deleted}")
        self.stdout.write(f"deleted_email   : {user.deleted_email}")
        self.stdout.write(f"date_joined     : {user.date_joined}")
        self.stdout.write(f"last_login      : {user.last_login}")
        self.stdout.write(f"password hash   : {user.password[:30]}...")
        self.stdout.write("")

        blockers = []
        if user.is_deleted:
            blockers.append("User is soft-deleted (won't be found by User.objects)")
        if not user.is_active:
            blockers.append("User is not active")
        if not user.is_verified:
            blockers.append("User is not verified")
        if not user.password or user.password.startswith("!"):
            blockers.append("Password hash is unusable (! prefix)")

        if blockers:
            self.stdout.write(self.style.ERROR("Login blockers:"))
            for b in blockers:
                self.stdout.write(f"  ✗ {b}")
        else:
            self.stdout.write(self.style.SUCCESS("No login blockers detected"))
