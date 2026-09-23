from datetime import timedelta

from django.utils import timezone

from drivers.models import DriverSlot
from .models import Booking

CONFIRMATION_WINDOW = timedelta(minutes=30)
SLOT_CAPACITY = 4


def reserved_driver_slots():
    """Reservations that still count toward the four-booking slot limit."""
    return DriverSlot.objects.exclude(
        booking__status__in=[
            Booking.BookingStatus.CANCELLED
        ]
    ).exclude(
        booking__status=Booking.BookingStatus.PENDING,
        booking__created_at__lte=timezone.now() - CONFIRMATION_WINDOW,
    )
