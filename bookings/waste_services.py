from decimal import Decimal, ROUND_HALF_UP

from django.core.exceptions import ValidationError
from django.db import transaction

from .models import Booking, BookingWasteItem
from .services import create_booking


def update_totals(booking):
    items = list(
        booking.waste_items.values_list(
            "estimated_weight", "subcategory__category__price_per_kg"
        )
    )
    booking.estimated_weight = sum((weight for weight, _ in items), Decimal("0.00"))
    booking.estimated_payout = sum(
        (
            (weight * price).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
            for weight, price in items
        ),
        Decimal("0.00"),
    )
    booking.save(update_fields=["estimated_weight", "estimated_payout", "updated_at"])


@transaction.atomic
def create_waste_booking(*, waste_items, **data):
    if not waste_items:
        raise ValidationError({"waste_items": "Select at least one waste item."})
    data.pop("estimated_weight", None)
    booking = create_booking(booking_type=Booking.BookingType.WASTE, **data)
    for item in waste_items:
        BookingWasteItem.objects.create(booking=booking, **item)
    update_totals(booking)
    return booking


@transaction.atomic
def add_item(*, booking, subcategory, estimated_weight):
    booking = Booking.objects.select_for_update().get(
        pk=booking.pk, booking_type=Booking.BookingType.WASTE
    )
    item = BookingWasteItem.objects.create(
        booking=booking, subcategory=subcategory, estimated_weight=estimated_weight
    )
    update_totals(booking)
    return item


@transaction.atomic
def update_item(item, **changes):
    booking = Booking.objects.select_for_update().get(pk=item.booking_id)
    item = BookingWasteItem.objects.get(pk=item.pk)
    for field in ("subcategory", "estimated_weight"):
        if field in changes:
            setattr(item, field, changes[field])
    item.save(update_fields=["subcategory", "estimated_weight", "updated_at"])
    update_totals(booking)
    return item


@transaction.atomic
def delete_item(item):
    booking = Booking.objects.select_for_update().get(pk=item.booking_id)
    BookingWasteItem.objects.filter(pk=item.pk).delete()
    update_totals(booking)
