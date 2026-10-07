import random
from datetime import datetime

from django.core.exceptions import ValidationError
from django.db.models import Count
from django.utils import timezone

from drivers.models import DriverProfile, DriverSlot
from users.models import User
from catalog.models import TimeSlot

from .exceptions import NoSlotAvailable, NoDriversAvailable
from .models import Booking
from .capacity import max_bookings_per_driver_slot, occupied_slot_capacity


def slot_is_future(slot, scheduled_date):
    slot_start = timezone.make_aware(datetime.combine(scheduled_date, slot.start_time))
    return slot_start > timezone.now()


def drivers_serving_pincode(pincode):
    return DriverProfile.objects.filter(
        is_available=True,
        user__is_active=True,
        user__user_type=User.UserType.DRIVER,
        service_pincodes__pincode=pincode,
        service_pincodes__is_active=True,
        service_pincodes__service_area__is_active=True,
    ).distinct()


def assign_driver(slot, scheduled_date, pincode):
    driver_capacity = max_bookings_per_driver_slot()
    candidate_ids = list(drivers_serving_pincode(pincode).values_list("pk", flat=True))
    if not candidate_ids:
        return None
    reservations = (
        DriverSlot.objects.filter(
            driver_id__in=candidate_ids,
            slot=slot,
            date=scheduled_date,
        )
        .values("driver_id")
        .annotate(count=Count("pk"))
    )
    counts = {row["driver_id"]: row["count"] for row in reservations}
    candidate_ids = [
        candidate_id
        for candidate_id in candidate_ids
        if counts.get(candidate_id, 0) < driver_capacity
    ]
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
            driver = DriverProfile.objects.select_for_update(of=("self",)).get(
                pk=chosen_id
            )
        except DriverProfile.DoesNotExist:
            candidate_ids.remove(chosen_id)
            continue

        if (
            drivers_serving_pincode(pincode).filter(pk=chosen_id).exists()
            and DriverSlot.objects.filter(
                driver_id=chosen_id, slot=slot, date=scheduled_date
            ).count()
            < driver_capacity
        ):
            return driver

        candidate_ids.remove(chosen_id)
    return None


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
    source=Booking.BookingSource.CUSTOMER,
):
    """Create a booking and reserve capacity inside the caller's transaction."""

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

    driver = assign_driver(slot, scheduled_date, pincode)
    if driver is None:
        raise NoDriversAvailable()

    now = timezone.now()
    booking = Booking(
        customer=customer,
        driver=driver,
        address=address,
        slot=slot,
        scheduled_date=scheduled_date,
        booking_type=booking_type,
        source=source,
        assigned_at=now if driver is not None else None,
        confirmed_at=now if source == Booking.BookingSource.ADMIN else None,
        estimated_weight=estimated_weight,
        note=note,
        estimated_payout=estimated_payout,
    )
    booking.save()
    DriverSlot.objects.create(
        driver=driver,
        slot=slot,
        date=scheduled_date,
        booking=booking,
    )
    return booking


def reassign_booking(booking, new_driver):
    booking = Booking.objects.select_for_update().get(pk=booking.pk)
    if new_driver.pk == booking.driver_id:
        raise ValidationError("Select a different driver.")
    if booking.address.pincode_id is None:
        raise ValidationError("The booking address has no service pincode.")
    try:
        new_driver = DriverProfile.objects.select_for_update(of=("self",)).get(
            pk=new_driver.pk
        )
    except DriverProfile.DoesNotExist as exc:
        raise ValidationError("Select an existing driver.") from exc

    if (
        not drivers_serving_pincode(booking.address.pincode.pincode)
        .filter(pk=new_driver.pk)
        .exists()
    ):
        raise ValidationError("The driver is unavailable for this pincode.")

    if (
        DriverSlot.objects.filter(
            driver=new_driver,
            slot=booking.slot,
            date=booking.scheduled_date,
        ).count()
        >= max_bookings_per_driver_slot()
    ):
        raise ValidationError("The driver has no capacity for this slot.")

    try:
        reservation = DriverSlot.objects.select_for_update().get(booking=booking)
    except DriverSlot.DoesNotExist as exc:
        raise ValidationError("The booking has no driver reservation.") from exc
    reservation.driver = new_driver
    reservation.save(update_fields=["driver"])
    booking.driver = new_driver
    booking.save()
    return booking
