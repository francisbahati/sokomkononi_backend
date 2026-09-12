from django.core.management.base import BaseCommand

from apps.boosting.models import BoostPackage


class Command(BaseCommand):
    help = "Creates or updates the default SokoMkononi boost packages."

    PACKAGES = [
        {
            "name": "Starter Boost",
            "duration_hours": 24,
            "price": 5000,
            "description": "Boost tangazo lako kwa siku 1.",
            "ordering": 1,
        },
        {
            "name": "Standard Boost",
            "duration_hours": 72,
            "price": 12000,
            "description": "Boost tangazo lako kwa siku 3.",
            "ordering": 2,
        },
        {
            "name": "Premium Boost",
            "duration_hours": 168,
            "price": 25000,
            "description": "Boost tangazo lako kwa siku 7.",
            "ordering": 3,
        },
        {
            "name": "Ultra Boost",
            "duration_hours": 336,
            "price": 40000,
            "description": "Boost tangazo lako kwa siku 14.",
            "ordering": 4,
        },
    ]

    def handle(self, *args, **options):
        for package_data in self.PACKAGES:
            package, created = BoostPackage.objects.update_or_create(
                name=package_data["name"],
                defaults={
                    "duration_hours": package_data["duration_hours"],
                    "price": package_data["price"],
                    "description": package_data["description"],
                    "ordering": package_data["ordering"],
                    "is_active": True,
                },
            )

            if created:
                self.stdout.write(
                    self.style.SUCCESS(
                        f"Created: {package.name}"
                    )
                )
            else:
                self.stdout.write(
                    self.style.SUCCESS(
                        f"Updated: {package.name}"
                    )
                )

        self.stdout.write(
            self.style.SUCCESS(
                "Boost packages seeded successfully."
            )
        )