"""
Reproduce a login attempt exactly as the API would, and print the
precise failure reason.

Usage:
    python manage.py diagnose_login user@example.com theirpassword
"""
from django.core.management.base import BaseCommand

from apps.accounts.models import User
from apps.accounts.serializers import LoginSerializer


class Command(BaseCommand):
    help = "Diagnose why a user can't log in."

    def add_arguments(self, parser):
        parser.add_argument("email", type=str)
        parser.add_argument("password", type=str)

    def handle(self, *args, **options):
        email = options["email"].strip().lower()
        password = options["password"]

        self.stdout.write("=" * 60)
        self.stdout.write(f" LOGIN DIAGNOSTIC :: {email}")
        self.stdout.write("=" * 60)

        # Step 1: does the user exist?
        user = User.all_objects.filter(email__iexact=email).first()
        if not user:
            self.stdout.write(self.style.ERROR(
                "✗ No user found with that email (including soft-deleted rows)."
            ))
            self.stdout.write("")
            self.stdout.write("→ The frontend is submitting a different email, or")
            self.stdout.write("  the user was hard-deleted. Check the DB directly:")
            self.stdout.write(f"    SELECT id, email, deleted_email FROM users WHERE deleted_email ILIKE '%{email}%';")
            return

        self.stdout.write(f"✓ User found: id={user.pk}")
        self.stdout.write("")

        # Step 2: run the exact serializer used by the API
        self.stdout.write("Running LoginSerializer exactly as the API does…")
        serializer = LoginSerializer(data={
            "identifier": email,
            "password": password,
        })

        if serializer.is_valid():
            self.stdout.write(self.style.SUCCESS(
                "✓ Login would SUCCEED with these credentials."
            ))
            return

        self.stdout.write(self.style.ERROR("✗ Login would FAIL."))
        self.stdout.write("")
        self.stdout.write("Serializer errors:")
        for field, errors in serializer.errors.items():
            for err in (errors if isinstance(errors, list) else [errors]):
                self.stdout.write(f"    {field}: {err}")
        self.stdout.write("")

        # Step 3: break down the failure so you know the fix
        self.stdout.write("Raw state of the user row:")
        self.stdout.write(f"    is_active   : {user.is_active}")
        self.stdout.write(f"    is_verified : {user.is_verified}")
        self.stdout.write(f"    is_deleted  : {user.is_deleted}")
        self.stdout.write(f"    is_staff    : {user.is_staff}")
        self.stdout.write(f"    password    : {user.password[:40]}…")
        self.stdout.write("")

        self.stdout.write("Password check:")
        pwd_ok = user.check_password(password)
        self.stdout.write(f"    check_password() : {pwd_ok}")
        self.stdout.write("")

        self.stdout.write("Likely fix:")
        if user.is_deleted:
            self.stdout.write("    → The user is soft-deleted. Run:")
            self.stdout.write(f"       python manage.py shell -c \"from apps.accounts.models import User; u = User.all_objects.get(pk={user.pk}); u.restore()\"")
        elif not pwd_ok:
            self.stdout.write("    → Password is wrong. Either the user mistyped, or the")
            self.stdout.write("      account was created with a hash that isn't what you expect.")
        elif not user.is_active:
            self.stdout.write("    → Account is deactivated. Reactivate:")
            self.stdout.write(f"       python manage.py shell -c \"from apps.accounts.models import User; User.objects.filter(pk={user.pk}).update(is_active=True)\"")
        elif not user.is_verified:
            self.stdout.write("    → Account is unverified. This is the most common cause.")
            self.stdout.write("      Fix options:")
            self.stdout.write(f"       a) python manage.py force_verify {email}")
            self.stdout.write("       b) python manage.py force_verify         # all users")
        else:
            self.stdout.write("    → Multiple causes may apply; see errors above.")
