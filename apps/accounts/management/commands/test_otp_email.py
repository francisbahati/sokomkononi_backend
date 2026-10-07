"""
Send a REAL OTP email to a specific address and print the result.

Usage:
    python manage.py test_otp_email someone@example.com

Checks the whole SMTP chain end-to-end. If this fails, the issue is
SMTP config, not Celery.
"""
import sys
import traceback
import time

from django.conf import settings
from django.core.management.base import BaseCommand
from django.core.mail import send_mail


class Command(BaseCommand):
    help = "Send a live test email and report the SMTP result."

    def add_arguments(self, parser):
        parser.add_argument("recipient", type=str)

    def handle(self, *args, **options):
        recipient = options["recipient"]

        self.stdout.write("=" * 70)
        self.stdout.write(" EMAIL DIAGNOSTIC")
        self.stdout.write("=" * 70)
        self.stdout.write(f"EMAIL_BACKEND       : {settings.EMAIL_BACKEND}")
        self.stdout.write(f"EMAIL_HOST          : {settings.EMAIL_HOST}")
        self.stdout.write(f"EMAIL_PORT          : {settings.EMAIL_PORT}")
        self.stdout.write(f"EMAIL_USE_TLS       : {settings.EMAIL_USE_TLS}")
        self.stdout.write(f"EMAIL_HOST_USER     : {settings.EMAIL_HOST_USER}")
        self.stdout.write(f"EMAIL_HOST_PASSWORD : {'***' if settings.EMAIL_HOST_PASSWORD else 'MISSING'}")
        self.stdout.write(f"DEFAULT_FROM_EMAIL  : {settings.DEFAULT_FROM_EMAIL}")
        self.stdout.write("")
        self.stdout.write(f"Sending test email to {recipient} ...")

        t0 = time.time()
        try:
            sent = send_mail(
                subject="SokoMkononi — Test email",
                message=(
                    "Ujumbe huu ni wa majaribio tu.\n\n"
                    "Kama unaona ujumbe huu, SMTP inafanya kazi vizuri."
                ),
                from_email=settings.DEFAULT_FROM_EMAIL,
                recipient_list=[recipient],
                fail_silently=False,
            )
            elapsed = time.time() - t0
            if sent == 1:
                self.stdout.write(self.style.SUCCESS(
                    f"✓ Email sent in {elapsed:.2f}s"
                ))
                self.stdout.write("")
                self.stdout.write(
                    "Check the inbox (and spam folder). If it arrived, "
                    "your SMTP config is correct."
                )
            else:
                self.stdout.write(self.style.ERROR(
                    f"✗ send_mail returned {sent} (expected 1)"
                ))
                sys.exit(1)

        except Exception as exc:
            elapsed = time.time() - t0
            self.stdout.write(self.style.ERROR(
                f"✗ SMTP FAILED after {elapsed:.2f}s: {type(exc).__name__}: {exc}"
            ))
            self.stdout.write("")
            self.stdout.write("Full traceback:")
            self.stdout.write(traceback.format_exc())
            self.stdout.write("")
            self.stdout.write("Common causes:")
            self.stdout.write("  - Wrong EMAIL_HOST / EMAIL_HOST_USER / EMAIL_HOST_PASSWORD")
            self.stdout.write("  - Gmail: you must use an App Password, not your normal password")
            self.stdout.write("  - Network: firewall blocking outbound port 587")
            self.stdout.write("  - From address must match EMAIL_HOST_USER (for Gmail)")
            sys.exit(1)
