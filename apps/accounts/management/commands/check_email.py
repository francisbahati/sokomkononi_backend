"""
Send a test email and print Celery + SMTP status.

Usage:
    python manage.py check_email you@example.com
"""
import os

from django.conf import settings
from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = "Send a test OTP email and report Celery + SMTP diagnostics."

    def add_arguments(self, parser):
        parser.add_argument("recipient", type=str)

    def handle(self, *args, **options):
        recipient = options["recipient"]

        self.stdout.write("============================================")
        self.stdout.write(" Email + Celery diagnostics")
        self.stdout.write("============================================")

        self.stdout.write(f"EMAIL_BACKEND      : {settings.EMAIL_BACKEND}")
        self.stdout.write(f"EMAIL_HOST         : {settings.EMAIL_HOST}")
        self.stdout.write(f"EMAIL_PORT         : {settings.EMAIL_PORT}")
        self.stdout.write(f"EMAIL_USE_TLS      : {settings.EMAIL_USE_TLS}")
        self.stdout.write(f"EMAIL_HOST_USER    : {settings.EMAIL_HOST_USER}")
        self.stdout.write(
            f"EMAIL_HOST_PASSWORD set: {bool(settings.EMAIL_HOST_PASSWORD)}"
        )
        self.stdout.write(f"DEFAULT_FROM_EMAIL : {settings.DEFAULT_FROM_EMAIL}")
        self.stdout.write("")

        # --- Celery broker check ---
        self.stdout.write("Celery broker:")
        self.stdout.write(f"  CELERY_BROKER_URL     : {settings.CELERY_BROKER_URL}")
        self.stdout.write(
            f"  CELERY_RESULT_BACKEND : {settings.CELERY_RESULT_BACKEND}"
        )

        try:
            from config.celery import app as celery_app
            conn = celery_app.connection()
            conn.ensure_connection(max_retries=2, timeout=3)
            self.stdout.write(self.style.SUCCESS("  broker reachable ✓"))
        except Exception as exc:
            self.stdout.write(self.style.ERROR(f"  broker unreachable ✗ {exc}"))

        self.stdout.write("")

        # --- Send test email synchronously ---
        self.stdout.write("Sending test email synchronously...")
        from apps.accounts.services import send_email_otp
        try:
            send_email_otp(recipient, "123456")
            self.stdout.write(
                self.style.SUCCESS(f"  sync send OK → {recipient}")
            )
        except Exception as exc:
            self.stdout.write(self.style.ERROR(f"  sync send FAILED: {exc}"))

        self.stdout.write("")

        # --- Send via Celery (with fallback) ---
        self.stdout.write("Sending test email via _dispatch_email (Celery → sync)...")
        from apps.accounts.services import _dispatch_email
        try:
            _dispatch_email(
                "send_email_otp_task", send_email_otp, recipient, "654321",
            )
            self.stdout.write(
                self.style.SUCCESS("  dispatch OK — check inbox")
            )
        except Exception as exc:
            self.stdout.write(self.style.ERROR(f"  dispatch FAILED: {exc}"))

        self.stdout.write("")
        self.stdout.write("Done.")
