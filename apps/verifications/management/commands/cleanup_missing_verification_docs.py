from django.core.management.base import BaseCommand
from apps.verifications.models import VerificationDocument


class Command(BaseCommand):
    help = "Find/delete verification docs whose file is missing in storage."

    def add_arguments(self, parser):
        parser.add_argument("--apply", action="store_true")
        parser.add_argument("--limit", type=int, default=0)

    def handle(self, *args, **opts):
        qs = VerificationDocument.objects.all().order_by("pk")
        if opts["limit"]:
            qs = qs[: opts["limit"]]

        missing = []
        for doc in qs.iterator():
            if not doc.file:
                continue
            try:
                if not doc.file.storage.exists(doc.file.name):
                    missing.append(doc)
                    self.stdout.write(
                        self.style.WARNING(f"  ✗ #{doc.pk} {doc.file.name}")
                    )
            except Exception as exc:
                self.stdout.write(self.style.ERROR(f"  ! #{doc.pk}: {exc}"))

        self.stdout.write(f"\nMissing: {len(missing)}")
        if opts["apply"] and missing:
            ids = [d.pk for d in missing]
            VerificationDocument.objects.filter(pk__in=ids).delete()
            self.stdout.write(self.style.SUCCESS(f"Deleted {len(ids)} rows."))
        elif not opts["apply"]:
            self.stdout.write("DRY RUN — pass --apply to delete.")
