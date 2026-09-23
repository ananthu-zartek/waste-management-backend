from datetime import timedelta

from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone

from bookings.capacity import CONFIRMATION_WINDOW
from bookings.models import Booking, BookingCleanupState


class Command(BaseCommand):
    help = "Exit nonzero when booking cleanup has stalled or its backlog is overdue."

    def handle(self, *args, **options):
        threshold = timezone.now() - timedelta(minutes=15)
        state = BookingCleanupState.objects.filter(pk=1).first()
        if state is None or state.last_success_at < threshold:
            raise CommandError("Booking cleanup has not succeeded within 15 minutes.")
        overdue = Booking.objects.filter(
            source=Booking.BookingSource.CUSTOMER,
            status=Booking.BookingStatus.PENDING,
            created_at__lte=threshold - CONFIRMATION_WINDOW,
        ).count()
        if overdue:
            raise CommandError(
                f"Booking cleanup has {overdue} holds overdue by at least 15 minutes."
            )
        self.stdout.write("Booking cleanup is healthy.")
