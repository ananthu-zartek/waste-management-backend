from datetime import timedelta

from drivers.models import DriverSlot
from users.models import SystemConfiguration
from .models import Booking

CONFIRMATION_WINDOW = timedelta(minutes=90)
CAPACITY_STATUSES = (
    Booking.BookingStatus.PENDING,
    Booking.BookingStatus.ASSIGNED,
    Booking.BookingStatus.CONFIRMED,
    Booking.BookingStatus.IN_PROGRESS,
    Booking.BookingStatus.COMPLETED,
)


def max_bookings_per_driver_slot():
    configured = SystemConfiguration.objects.values_list(
        "max_bookings_per_driver_slot", flat=True
    ).first()
    return 4 if configured is None else configured


def occupied_slot_capacity(slot, scheduled_date):
    return Booking.objects.filter(
        slot=slot, scheduled_date=scheduled_date, status__in=CAPACITY_STATUSES
    ).count()


def reserved_driver_slots():
    """Capacity remains reserved until cancellation or expiry removes the row."""
    return DriverSlot.objects.all()
