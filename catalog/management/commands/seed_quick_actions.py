from django.core.management.base import BaseCommand

from catalog.models import QuickAction


QUICK_ACTIONS = (
    ("Schedule Pickup", "Book waste collection"),
    ("Sell Scrap", "Earn from scrap sale"),
    ("Recurring", "Weekly / monthly"),
    ("Track Pickup", "Live status"),
)


class Command(BaseCommand):
    help = "Create the default catalogue quick actions."

    def handle(self, *args, **options):
        created_count = 0
        for sort_order, (title, subtitle) in enumerate(QUICK_ACTIONS, start=1):
            _, created = QuickAction.objects.get_or_create(
                title=title,
                defaults={"subtitle": subtitle, "sort_order": sort_order},
            )
            created_count += created

        self.stdout.write(
            self.style.SUCCESS(f"Created {created_count} quick action(s).")
        )
