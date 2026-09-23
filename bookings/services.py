import hashlib
import json

from django.core.exceptions import ValidationError
from django.db import transaction
from django.db.models import Count, Q
from django.http import Http404
from django.utils import timezone

from drivers.models import DriverProfile, DriverSlot
from users.models import User

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


def eligible_drivers(slot, scheduled_date):
    reservations = reserved_driver_slots().filter(slot=slot, date=scheduled_date)
    return (
        DriverProfile.objects.filter(
            is_available=True,
            user__is_active=True,
            user__user_type=User.UserType.DRIVER,
        )
        .annotate(
            booking_count=Count(
                "driver_slots",
                filter=Q(driver_slots__in=reservations),
            )
        )
        .filter(booking_count__lt=SLOT_CAPACITY)
        .order_by("pk")
    )


def slot_is_future(slot, scheduled_date):
    now = timezone.localtime()
    return scheduled_date > now.date() or (
        scheduled_date == now.date() and slot.start_time > now.time()
    )


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
        raise ValidationError({"slot": "Select an active, future time slot."})
    if address.customer_id != customer.pk:
        raise ValidationError({"address": "The address must belong to the customer."})

    driver = None
    if source == Booking.BookingSource.CUSTOMER:
        candidates = eligible_drivers(slot, scheduled_date)
        if driver_id is not None:
            candidates = candidates.filter(pk=driver_id)
        # Lock drivers in ID order; count only after the driver lock is held.
        for candidate_id in candidates.values_list("pk", flat=True):
            candidate = (
                DriverProfile.objects.select_for_update(of=("self",))
                .filter(
                    pk=candidate_id,
                    is_available=True,
                    user__is_active=True,
                    user__user_type=User.UserType.DRIVER,
                )
                .first()
            )
            if candidate is None:
                continue
            count = (
                reserved_driver_slots()
                .filter(
                    driver=candidate,
                    slot=slot,
                    date=scheduled_date,
                )
                .count()
            )
            if count < SLOT_CAPACITY:
                driver = candidate
                break
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
    DriverProfile.objects.select_for_update().get(pk=reservation.driver_id)
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
