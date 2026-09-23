from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils import timezone

from bookings.exceptions import NoSlotAvailable
from bookings.models import Booking
from bookings.capacity import (
    CONFIRMATION_WINDOW,
    SLOT_CAPACITY,
    reserved_driver_slots,
)
from catalog.models import TimeSlot

from .models import DriverProfile, DriverSlot


def assign_booking(*, booking_id, driver_id):
    """Assign or reassign an existing booking to an explicitly selected driver."""
    with transaction.atomic():
        booking = Booking.objects.select_for_update().get(pk=booking_id)
        if booking.status in (
            Booking.BookingStatus.CANCELLED,
            Booking.BookingStatus.COMPLETED,
            Booking.BookingStatus.EXPIRED,
        ):
            raise ValidationError(
                "Cancelled, expired or completed bookings cannot be assigned."
            )

        # Use a consistent lock order when moving capacity between drivers.
        existing = DriverSlot.objects.filter(booking=booking).first()
        driver_ids = {driver_id}
        if existing:
            driver_ids.add(existing.driver_id)
        drivers = {
            driver.pk: driver
            for driver in DriverProfile.objects.select_for_update()
            .filter(pk__in=driver_ids)
            .order_by("pk")
        }
        if driver_id not in drivers:
            raise ValidationError({"driver": "The selected driver does not exist."})
        slot = TimeSlot.objects.get(pk=booking.slot_id)
        if not slot.is_active:
            raise ValidationError({"slot": "The selected slot must be active."})

        if (
            booking.status == Booking.BookingStatus.PENDING
            and timezone.now() >= booking.created_at + CONFIRMATION_WINDOW
        ):
            raise ValidationError("Booking confirmation window has expired.")
        if booking.source == Booking.BookingSource.CUSTOMER:
            occupied = (
                reserved_driver_slots()
                .filter(
                    driver_id=driver_id,
                    slot=slot,
                    date=booking.scheduled_date,
                )
                .exclude(booking=booking)
            )
            if occupied.count() >= SLOT_CAPACITY:
                raise NoSlotAvailable()

        if booking.driver_id != driver_id or booking.assigned_at is None:
            booking.assigned_at = timezone.now()
        booking.driver = drivers[driver_id]
        if (
            booking.status == Booking.BookingStatus.PENDING
            and booking.source == Booking.BookingSource.ADMIN
        ):
            booking.status = Booking.BookingStatus.ASSIGNED
        booking.save(update_fields=["driver", "status", "assigned_at", "updated_at"])

        if booking.source == Booking.BookingSource.ADMIN:
            if existing:
                existing.delete()
            return booking
        if existing and (
            existing.driver_id == driver_id
            and existing.slot_id == slot.pk
            and existing.date == booking.scheduled_date
        ):
            return booking
        if existing:
            existing.delete()
        DriverSlot.objects.create(
            driver=drivers[driver_id],
            slot=slot,
            date=booking.scheduled_date,
            booking=booking,
        )
        return booking
