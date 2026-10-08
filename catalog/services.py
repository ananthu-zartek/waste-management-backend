from bookings.models import Booking


CAPACITY_STATUSES = (
    Booking.BookingStatus.PENDING,
    Booking.BookingStatus.ASSIGNED,
    Booking.BookingStatus.CONFIRMED,
    Booking.BookingStatus.IN_PROGRESS,
    Booking.BookingStatus.COMPLETED,
)
