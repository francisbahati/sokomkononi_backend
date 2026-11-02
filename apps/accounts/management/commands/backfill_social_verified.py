# apps/accounts/management/commands/backfill_social_verified.py

from django.core.management.base import BaseCommand
from django.db import transaction

from apps.accounts.models import User


class Command(BaseCommand):
    help = (
        "Backfill email_verified=True kwa watumiaji wa zamani wa "
        "Google/Apple (hawana password, hawajathibitisha email)."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Onyesha watumiaji watakaobadilishwa, bila kubadilisha",
        )
        parser.add_argument(
            "--limit",
            type=int,
            default=20,
            help="Idadi ya watumiaji kuonyesha kwenye dry-run (default: 20)",
        )

    def handle(self, *args, **options):
        dry_run = options["dry_run"]
        limit = options["limit"]

        # Watumiaji wa social:
        #   - hawana password (password__startswith="!")
        #   - hawajathibitisha email (email_verified=False)
        #   - si staff (exclude admin)
        #   - active, not deleted
        qs = User.objects.filter(
            password__startswith="!",
            email_verified=False,
            is_staff=False,
            is_active=True,
            is_deleted=False,
        )

        total = qs.count()
        self.stdout.write(
            self.style.WARNING(
                f"Watumiaji {total} wanagunduliwa kama wa social "
                f"(hawana password, email_verified=False)"
            )
        )

        if dry_run:
            self.stdout.write("\n=== DRY RUN — watumiaji wa kwanza ===")
            for u in qs[:limit]:
                self.stdout.write(
                    f"  - id={u.id} email={u.email or '—'} "
                    f"name={u.name or '—'} "
                    f"created={u.created_at.strftime('%Y-%m-%d')}"
                )
            if total > limit:
                self.stdout.write(f"  ... na wengine {total - limit}")
            self.stdout.write(
                self.style.WARNING("\nDRY RUN — hakuna mabadiliko yaliyofanywa")
            )
            return

        with transaction.atomic():
            updated = qs.update(email_verified=True)

        self.stdout.write(
            self.style.SUCCESS(
                f"Watumiaji {updated} wamewekwa email_verified=True"
            )
        )