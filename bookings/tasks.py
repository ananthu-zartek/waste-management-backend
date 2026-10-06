from celery import shared_task
from django.db import transaction
from django.utils import timezone

from drivers.models import DriverSlot

from .capacity import CONFIRMATION_WINDOW
from .models import Booking


@shared_task
def expire_pending_bookings():
    """Release overdue holds, locking the same booking row as confirmation."""
    cutoff = timezone.now() - CONFIRMATION_WINDOW
    expired_count = 0
    for _ in range(500):
        with transaction.atomic():
            booking = (
                Booking.objects.select_for_update(skip_locked=True)
                .filter(
                    source=Booking.BookingSource.CUSTOMER,
                    status=Booking.BookingStatus.PENDING,
                    created_at__lte=cutoff,
                )
                .order_by("pk")
                .first()
            )
            if booking is None:
                break
            booking.status = Booking.BookingStatus.EXPIRED
            booking.expired_at = booking.created_at + CONFIRMATION_WINDOW
            booking.save(update_fields=["status", "expired_at", "updated_at"])
            expired_count += 1
    return expired_count
