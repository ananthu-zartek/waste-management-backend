from datetime import timedelta

from drivers.models import DriverSlot

CONFIRMATION_WINDOW = timedelta(minutes=30)
SLOT_CAPACITY = 4


def reserved_driver_slots():
    """Capacity remains reserved until cancellation or expiry removes the row."""
    return DriverSlot.objects.all()
