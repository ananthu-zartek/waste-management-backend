from decimal import Decimal, ROUND_HALF_UP

from django.core.exceptions import ValidationError
from django.db import transaction
from django.db.models import Sum

from .models import Booking, ScrapBooking, ScrapBookingItem
from .services import create_booking


def quote_scrap(items):
    if not items:
        raise ValidationError({"scrap_items": "Select at least one scrap item."})
    ids = [item["material"].pk for item in items]
    if len(ids) != len(set(ids)):
        raise ValidationError({"scrap_items": "Select each material only once."})
    result = []
    for item in items:
        material = item["material"]
        weight = Decimal(str(item["estimated_weight"]))
        result.append(
            {
                "material": material,
                "name": material.name,
                "estimated_weight": weight,
                "price_per_kg": material.price_per_kg,
                "estimated_payout": (weight * material.price_per_kg).quantize(
                    Decimal("0.01"), rounding=ROUND_HALF_UP
                ),
            }
        )
    return result


def update_totals(booking):
    totals = ScrapBookingItem.objects.filter(scrap_booking__booking=booking).aggregate(
        weight=Sum("estimated_weight", default=0),
        payout=Sum("estimated_payout", default=0),
    )
    booking.estimated_weight = totals["weight"]
    booking.estimated_payout = totals["payout"]
    booking.save(update_fields=["estimated_weight", "estimated_payout", "updated_at"])


@transaction.atomic
def create_scrap_booking(*, scrap_items, **data):
    quoted = quote_scrap(scrap_items)
    data.pop("estimated_weight", None)
    booking = create_booking(booking_type=Booking.BookingType.SCRAP, **data)
    scrap = ScrapBooking.objects.create(booking=booking)
    for entry, original in zip(quoted, scrap_items):
        ScrapBookingItem.objects.create(
            scrap_booking=scrap,
            material=entry["material"],
            name=original.get("name") or entry["name"],
            estimated_weight=entry["estimated_weight"],
            estimated_payout=entry["estimated_payout"],
        )
    update_totals(booking)
    return booking


@transaction.atomic
def add_item(*, scrap_booking, material, estimated_weight, name=""):
    booking = Booking.objects.select_for_update().get(
        pk=scrap_booking.booking_id, booking_type=Booking.BookingType.SCRAP
    )
    quote = quote_scrap([{"material": material, "estimated_weight": estimated_weight}])[
        0
    ]
    item = ScrapBookingItem.objects.create(
        scrap_booking=scrap_booking,
        material=material,
        name=name or material.name,
        estimated_weight=estimated_weight,
        estimated_payout=quote["estimated_payout"],
    )
    update_totals(booking)
    return item


@transaction.atomic
def update_item(item, **changes):
    booking = Booking.objects.select_for_update().get(pk=item.scrap_booking.booking_id)
    item = ScrapBookingItem.objects.select_related("material").get(pk=item.pk)
    for field in ("name", "estimated_weight"):
        if field in changes:
            setattr(item, field, changes[field])
    item.estimated_payout = (item.estimated_weight * item.material.price_per_kg).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    item.save(
        update_fields=["name", "estimated_weight", "estimated_payout", "updated_at"]
    )
    update_totals(booking)
    return item


@transaction.atomic
def delete_item(item):
    booking = Booking.objects.select_for_update().get(pk=item.scrap_booking.booking_id)
    ScrapBookingItem.objects.filter(pk=item.pk).delete()
    update_totals(booking)
