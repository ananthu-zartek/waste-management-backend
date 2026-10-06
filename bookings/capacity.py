from datetime import timedelta

from drivers.models import DriverSlot
from .models import Booking

CONFIRMATION_WINDOW = timedelta(minutes=90)
MAX_BOOKINGS_PER_DRIVER_SLOT = 4
CAPACITY_STATUSES = (
    Booking.BookingStatus.PENDING,
    Booking.BookingStatus.ASSIGNED,
    Booking.BookingStatus.CONFIRMED,
    Booking.BookingStatus.IN_PROGRESS,
    Booking.BookingStatus.COMPLETED,
)


def occupied_slot_capacity(slot, scheduled_date):
    return Booking.objects.filter(
        slot=slot, scheduled_date=scheduled_date, status__in=CAPACITY_STATUSES
    ).count()


def reserved_driver_slots():
    """Capacity remains reserved until cancellation or expiry removes the row."""
    return DriverSlot.objects.all()
