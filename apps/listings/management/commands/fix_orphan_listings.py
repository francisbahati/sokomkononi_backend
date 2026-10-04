"""
Assign a category to listings that have category = NULL.
Runs automatically on deploy via entrypoint.sh (see File 5).
"""
from django.core.management.base import BaseCommand

from apps.categories.models import Category
from apps.listings.models import Listing


class Command(BaseCommand):
    help = "Fix orphan listings whose category is NULL."

    def add_arguments(self, parser):
        parser.add_argument("--apply", action="store_true")
        parser.add_argument("--slug", default=None)
        parser.add_argument("--delete", action="store_true")

    def handle(self, *args, **opts):
        orphans = Listing.objects.filter(category__isnull=True)
        total = orphans.count()
        self.stdout.write("Found {} orphan listings.".format(total))

        if total == 0:
            return

        for l in orphans[:20]:
            self.stdout.write(
                "  id={} title={!r} price={}".format(l.id, l.title, l.price)
            )

        if not opts["apply"] and not opts["delete"]:
            self.stdout.write("DRY RUN — pass --apply or --delete.")
            return

        if opts["delete"]:
            deleted, _ = orphans.delete()
            self.stdout.write(self.style.SUCCESS(
                "Deleted {} orphan listings.".format(deleted)
            ))
            return

        slug = opts["slug"]
        if slug:
            cat = Category.objects.filter(slug=slug).first()
        else:
            cat = (
                Category.objects.filter(slug="nyumba-majengo").first()
                or Category.objects.first()
            )

        if not cat:
            self.stdout.write(self.style.ERROR("No category available."))
            return

        updated = orphans.update(category=cat)
        self.stdout.write(self.style.SUCCESS(
            "Assigned {} orphans to {}".format(updated, cat.slug)
        ))
