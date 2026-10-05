import random
from datetime import datetime

from django.core.exceptions import ValidationError
from django.db import transaction
from django.db.models import Count
from django.http import Http404
from django.utils import timezone

from drivers.models import DriverProfile, DriverSlot
from users.models import User
from catalog.models import TimeSlot
from catalog.services import validate_service_pincode

from .exceptions import NoSlotAvailable
from .models import Booking
from .capacity import (
    CONFIRMATION_WINDOW,
    occupied_slot_capacity,
    reserved_driver_slots,
)


def drivers_serving_pincode(pincode):
    return DriverProfile.objects.filter(
        is_available=True,
        user__is_active=True,
        user__user_type=User.UserType.DRIVER,
        service_pincodes__pincode=pincode,
        service_pincodes__is_active=True,
        service_pincodes__service_area__is_active=True,
    ).distinct()


def assign_driver(*, slot, scheduled_date, pincode, driver_id=None):
    """Choose a least-loaded eligible driver while the caller holds the slot lock."""
    candidate_ids = list(
        drivers_serving_pincode(pincode)
        .filter(**({"pk": driver_id} if driver_id is not None else {}))
        .values_list("pk", flat=True)
    )
    if not candidate_ids:
        return None

    reservations = (
        reserved_driver_slots()
        .filter(driver_id__in=candidate_ids, slot=slot, date=scheduled_date)
        .values("driver_id")
        .annotate(count=Count("pk"))
    )
    counts = {row["driver_id"]: row["count"] for row in reservations}
    while candidate_ids:
        lowest_count = min(
            counts.get(candidate_id, 0) for candidate_id in candidate_ids
        )
        least_loaded_ids = [
            candidate_id
            for candidate_id in candidate_ids
            if counts.get(candidate_id, 0) == lowest_count
        ]
        chosen_id = random.choice(least_loaded_ids)
        try:
            chosen = DriverProfile.objects.select_for_update(
                of=("self",), no_key=True
            ).get(pk=chosen_id)
        except DriverProfile.DoesNotExist:
            candidate_ids.remove(chosen_id)
            continue
        if drivers_serving_pincode(pincode).filter(pk=chosen_id).exists():
            return chosen
        candidate_ids.remove(chosen_id)
    return None


def slot_is_future(slot, scheduled_date):
    slot_start = timezone.make_aware(datetime.combine(scheduled_date, slot.start_time))
    return slot_start > timezone.now()


@transaction.atomic
def create_booking(
    *,
    customer,
    address,
    slot,
    scheduled_date,
    booking_type,
    estimated_weight=0,
    estimated_payout=0,
    note="",
    driver_id=None,
    source=Booking.BookingSource.CUSTOMER,
):
    """Create a booking and reserve customer capacity atomically."""
    slot = TimeSlot.objects.select_for_update().get(pk=slot.pk)
    if not slot.is_active or not slot_is_future(slot, scheduled_date):
        raise ValidationError("Select an active, future time slot.")
    if occupied_slot_capacity(slot, scheduled_date) >= slot.capacity:
        raise NoSlotAvailable()
    if address.customer_id != customer.pk:
        raise ValidationError("The address must belong to the customer.")
    if address.pincode_id is None:
        raise ValidationError("Select a supported pincode for this address.")
    pincode = address.pincode.pincode
    if (
        driver_id is not None
        and not DriverProfile.objects.filter(pk=driver_id).exists()
    ):
        raise ValidationError("Select a valid driver.")

    driver = None
    if source == Booking.BookingSource.CUSTOMER or driver_id is not None:
        driver = assign_driver(
            slot=slot,
            scheduled_date=scheduled_date,
            pincode=pincode,
            driver_id=driver_id,
        )
        if driver is None:
            raise NoSlotAvailable()
    else:
        validate_service_pincode(pincode)
    now = timezone.now()
    booking = Booking(
        customer=customer,
        driver=driver,
        address=address,
        slot=slot,
        scheduled_date=scheduled_date,
        booking_type=booking_type,
        source=source,
        status=(
            Booking.BookingStatus.PENDING
            if source == Booking.BookingSource.CUSTOMER
            else Booking.BookingStatus.CONFIRMED
        ),
        assigned_at=now if driver is not None else None,
        confirmed_at=now if source == Booking.BookingSource.ADMIN else None,
        estimated_weight=estimated_weight,
        note=note,
        estimated_payout=estimated_payout,
    )
    booking.save()
    if driver is not None:
        DriverSlot.objects.create(
            driver=driver, slot=slot, date=scheduled_date, booking=booking
        )
    return booking


@transaction.atomic
def confirm_booking(*, booking_id, customer_id):
    try:
        booking = Booking.objects.select_for_update().get(
            pk=booking_id,
            customer_id=customer_id,
            source=Booking.BookingSource.CUSTOMER,
        )
    except Booking.DoesNotExist as exc:
        raise Http404("Booking not found.") from exc
    if booking.status != Booking.BookingStatus.PENDING:
        raise ValidationError("Booking cannot be confirmed.")
    reservation = DriverSlot.objects.filter(booking=booking).first()
    if reservation is None:
        raise ValidationError("Booking has no reserved capacity.")
    if reservation.driver_id != booking.driver_id:
        raise ValidationError(
            {"driver": "The booking driver does not match its reservation."}
        )
    if booking.address.pincode_id is None:
        raise ValidationError(
            {"address": "Select a supported pincode for this address."}
        )
    validate_service_pincode(booking.address.pincode.pincode, booking.driver)
    now = timezone.now()
    if now >= booking.created_at + CONFIRMATION_WINDOW:
        raise ValidationError("Booking confirmation window has expired.")
    booking.status = Booking.BookingStatus.CONFIRMED
    booking.confirmed_at = now
    booking.save(update_fields=["status", "confirmed_at", "updated_at"])
    return booking


@transaction.atomic
def cancel_booking(*, booking_id, other_notes=None):
    """Keep the booking history and release its occupied customer capacity."""
    try:
        booking = Booking.objects.select_for_update().get(pk=booking_id)
    except Booking.DoesNotExist as exc:
        raise Http404("Booking not found.") from exc
    if booking.status == Booking.BookingStatus.COMPLETED:
        raise ValidationError("Completed bookings cannot be cancelled.")
    if booking.status == Booking.BookingStatus.EXPIRED:
        raise ValidationError("Expired bookings cannot be cancelled.")
    driver_slot = DriverSlot.objects.filter(booking=booking).first()
    if driver_slot:
        DriverProfile.objects.select_for_update().get(pk=driver_slot.driver_id)
    update_fields = []
    if (
        booking.status != Booking.BookingStatus.CANCELLED
        or booking.cancelled_at is None
    ):
        booking.status = Booking.BookingStatus.CANCELLED
        booking.cancelled_at = timezone.now()
        update_fields.extend(["status", "cancelled_at"])
    if other_notes is not None:
        booking.other_notes = other_notes
        update_fields.append("other_notes")
    if update_fields:
        booking.save(update_fields=[*update_fields, "updated_at"])
    if driver_slot:
        driver_slot.delete()
    return booking
