from django.core.exceptions import ValidationError

from .models import Booking, BookingWasteItem
from .services import create_booking


def create_waste_booking(*, waste_items, **data):
    if not waste_items:
        raise ValidationError({"waste_items": "Select at least one waste item."})
    booking = create_booking(booking_type=Booking.BookingType.WASTE, **data)
    for item in waste_items:
        BookingWasteItem.objects.create(booking=booking, **item)
    return booking
