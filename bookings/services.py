import hashlib
import json
import random
from datetime import datetime

from django.core.exceptions import ValidationError
from django.db import transaction
from django.db.models import Count, Q
from django.http import Http404
from django.utils import timezone

from drivers.models import DriverProfile, DriverSlot
from users.models import User
from catalog.services import validate_service_pincode

from .exceptions import IdempotencyConflict, NoSlotAvailable
from .models import Booking, BookingRequest
from .capacity import (
    CONFIRMATION_WINDOW,
    SLOT_CAPACITY,
    reserved_driver_slots,
)


def get_booking_request(*, customer, key, payload, role):
    """Call within the transaction that creates the booking and stores its response."""
    fingerprint = hashlib.sha256(
        json.dumps(
            {"payload": payload, "role": role},
            sort_keys=True,
            separators=(",", ":"),
        ).encode()
    ).hexdigest()
    attempt, _ = BookingRequest.objects.get_or_create(
        customer=customer, key=key, defaults={"fingerprint": fingerprint}
    )
    attempt = BookingRequest.objects.select_for_update().get(pk=attempt.pk)
    if attempt.fingerprint != fingerprint:
        raise IdempotencyConflict()
    return attempt


def eligible_drivers(slot, scheduled_date, pincode):
    reservations = reserved_driver_slots().filter(slot=slot, date=scheduled_date)
    return (
        DriverProfile.objects.filter(
            is_available=True,
            user__is_active=True,
            user__user_type=User.UserType.DRIVER,
            service_pincodes__pincode=pincode,
            service_pincodes__is_active=True,
            service_pincodes__service_area__is_active=True,
        )
        .annotate(
            booking_count=Count(
                "driver_slots",
                filter=Q(driver_slots__in=reservations),
            )
        )
        .distinct()
    )


def assign_driver(*, slot, scheduled_date, pincode, driver_id=None):
    """Lock eligible drivers, then assign the least-loaded driver at random on ties."""
    candidate_ids = list(
        eligible_drivers(slot, scheduled_date, pincode)
        .filter(**({"pk": driver_id} if driver_id is not None else {}))
        .values_list("pk", flat=True)
    )
    if not candidate_ids:
        return None

    # Lock in stable order so overlapping assignment transactions cannot deadlock.
    candidates = list(
        DriverProfile.objects.filter(pk__in=candidate_ids)
        .select_for_update(of=("self",))
        .order_by("pk")
    )
    reservations = (
        reserved_driver_slots()
        .filter(driver__in=candidates, slot=slot, date=scheduled_date)
        .values("driver_id")
        .annotate(count=Count("pk"))
    )
    counts = {row["driver_id"]: row["count"] for row in reservations}
    lowest_count = min(counts.get(candidate.pk, 0) for candidate in candidates)
    least_loaded = [
        candidate
        for candidate in candidates
        if counts.get(candidate.pk, 0) == lowest_count
    ]
    if lowest_count >= SLOT_CAPACITY:
        return None
    return random.choice(least_loaded)


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
    if not slot.is_active or not slot_is_future(slot, scheduled_date):
        raise ValidationError("Select an active, future time slot.")
    if address.customer_id != customer.pk:
        raise ValidationError("The address must belong to the customer.")
    if address.pincode_id is None:
        raise ValidationError("Select a supported pincode for this address.")
    pincode = address.pincode.pincode
    validate_service_pincode(pincode)

    driver = None
    if source == Booking.BookingSource.CUSTOMER or driver_id is not None:
        if driver_id is not None:
            try:
                selected_driver = DriverProfile.objects.get(pk=driver_id)
            except DriverProfile.DoesNotExist as exc:
                raise ValidationError("Select a valid driver.") from exc
            validate_service_pincode(pincode, selected_driver)
        driver = assign_driver(
            slot=slot,
            scheduled_date=scheduled_date,
            pincode=pincode,
            driver_id=driver_id,
        )
        if driver is None:
            raise NoSlotAvailable()

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
