# apps/accounts/management/commands/reset_2fa.py
"""
Zima 2FA ya mtumiaji (kwa support, mf. admin amepoteza simu na recovery codes).

    python manage.py reset_2fa admin@sokomkononi.co.tz

Mtumiaji ataingia kwa nenosiri tu kisha aombwe kuwasha 2FA upya.
Endesha kutoka server pekee — haipatikani kupitia API.
"""
from django.core.management.base import BaseCommand, CommandError

from apps.accounts.models import User, UserTOTP


class Command(BaseCommand):
    help = "Zima 2FA ya mtumiaji (secret na recovery codes vinafutwa)."

    def add_arguments(self, parser):
        parser.add_argument("email", help="Barua pepe ya mtumiaji")

    def handle(self, *args, **opts):
        email = opts["email"].strip()
        user = User.all_objects.filter(email__iexact=email).first()
        if not user:
            raise CommandError(f"Mtumiaji hapatikani: {email}")

        totp = UserTOTP.objects.filter(user=user).first()
        if not totp or not totp.enabled:
            self.stdout.write(self.style.WARNING(f"{email}: 2FA haikuwa imewashwa."))
            return

        totp.enabled = False
        totp.secret = ""
        totp.recovery_codes = []
        totp.save(update_fields=["enabled", "secret", "recovery_codes"])
        self.stdout.write(self.style.SUCCESS(f"{email}: 2FA imezimwa. Aiwashe upya baada ya kuingia."))
