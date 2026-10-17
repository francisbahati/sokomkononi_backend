"""Generate WebP variants for ListingImage rows missing them."""
import uuid
import logging

from django.core.management.base import BaseCommand

from apps.listings.image_variants import generate_webp_variants
from apps.listings.models import ListingImage

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = "Generate WebP variants for existing ListingImage rows."

    def add_arguments(self, parser):
        parser.add_argument("--limit", type=int, default=0)
        parser.add_argument("--dry-run", action="store_true")

    def handle(self, *args, **opts):
        qs = (
            ListingImage.objects
            .filter(thumb__isnull=True)
            .exclude(image="")
            .order_by("pk")
        )
        if opts["limit"]:
            qs = qs[: opts["limit"]]
        total = qs.count()
        self.stdout.write(f"Found {total} image(s) without variants")

        if opts["dry_run"]:
            self.stdout.write("(dry-run — nothing changed)")
            return

        ok = failed = 0
        for img in qs.iterator():
            try:
                try:
                    img.image.open("rb")
                except Exception:
                    pass
                variants = generate_webp_variants(img.image)
                try:
                    img.image.close()
                except Exception:
                    pass

                updates = {}
                for name, content in variants.items():
                    field = getattr(img, name)
                    field.save(
                        f"{img.listing_id}_{uuid.uuid4().hex[:8]}_{name}.webp",
                        content,
                        save=False,
                    )
                    updates[name] = field.name

                ListingImage.objects.filter(pk=img.pk).update(**updates)
                ok += 1
                if ok % 25 == 0:
                    self.stdout.write(f"  ... {ok}/{total}")
            except Exception as exc:
                failed += 1
                self.stderr.write(f"  FAILED #{img.pk}: {exc}")

        self.stdout.write(
            self.style.SUCCESS(f"Done. ok={ok} failed={failed}")
        )
