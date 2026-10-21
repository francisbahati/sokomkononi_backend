"""
Futa fee rules zisizo na category halali (orphans) kwenye backend.

Tumia:
    python manage.py cleanup_orphan_fee_rules
    python manage.py cleanup_orphan_fee_rules --dry-run
    python manage.py cleanup_orphan_fee_rules --hard-delete
    python manage.py cleanup_orphan_fee_rules --no-slug-check
"""
from django.core.management.base import BaseCommand

from apps.categories.models import Category
from apps.listings.models import ListingFeeRule


class Command(BaseCommand):
    help = "Futa fee rules zisizo na category halali (orphans)"

    def add_arguments(self, parser):
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Onyesha tu bila kufuta",
        )
        parser.add_argument(
            "--hard-delete",
            action="store_true",
            help="Futa kabisa (hard delete) badala ya soft delete",
        )
        parser.add_argument(
            "--no-slug-check",
            action="store_true",
            help="Futa tu rules zenye category=NULL (usiangalie slug)",
        )

    def handle(self, *args, **options):
        dry_run = options["dry_run"]
        hard_delete = options["hard_delete"]
        no_slug_check = options["no_slug_check"]

        # Orphans mbili aina:
        #   A) category = NULL (hakuna FK)
        #   B) category_slug haipo kwenye Category.slug
        null_cat_qs = ListingFeeRule.objects.filter(
            category__isnull=True,
            is_deleted=False,
        )

        if no_slug_check:
            orphans = null_cat_qs
        else:
            valid_slugs = set(
                Category.objects.filter(is_deleted=False)
                .values_list("slug", flat=True)
            )
            slug_orphans_qs = (
                ListingFeeRule.objects
                .filter(is_deleted=False)
                .exclude(category_slug__in=valid_slugs)
            )
            orphans = (null_cat_qs | slug_orphans_qs).distinct()

        orphans = orphans.order_by("id")
        count = orphans.count()

        if count == 0:
            self.stdout.write(
                self.style.SUCCESS("Hakuna orphan fee rule(s) zilizopatikana.")
            )
            return

        self.stdout.write(self.style.WARNING(
            f"Orphan fee rule(s): {count}"
        ))

        for rule in orphans:
            cat_label = (
                rule.category.slug if rule.category_id
                else (rule.category_slug or "—")
            )
            self.stdout.write(
                f"  #{rule.id} — {rule.name} "
                f"(category: {cat_label}, "
                f"category_id: {rule.category_id or '—'}, "
                f"active: {rule.is_active})"
            )

        if dry_run:
            self.stdout.write(self.style.WARNING(
                "\nDRY RUN — hakuna kitu kilichofutwa. "
                "Ondoa --dry-run ili kufuta."
            ))
            return

        deleted = failed = 0
        for rule in orphans:
            try:
                if hard_delete:
                    rule.hard_delete()
                else:
                    rule.delete(by=None, reason="Orphan cleanup")
                deleted += 1
            except Exception as exc:
                failed += 1
                self.stderr.write(
                    self.style.ERROR(f"Failed to delete #{rule.id}: {exc}")
                )

        self.stdout.write(self.style.SUCCESS(
            f"\nDeleted: {deleted} "
            f"({'hard' if hard_delete else 'soft'})"
        ))
        if failed:
            self.stdout.write(self.style.ERROR(f"Failed: {failed}"))