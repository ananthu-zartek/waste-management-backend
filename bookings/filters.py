from django_filters import rest_framework as filters
from django.utils import timezone

from .models import Booking


class BookingFilter(filters.FilterSet):
    status = filters.ChoiceFilter(choices=Booking.BookingStatus.choices)
    date = filters.DateFilter(field_name="scheduled_date")
    booking_type = filters.ChoiceFilter(choices=Booking.BookingType.choices)
    tab = filters.ChoiceFilter(
        choices=[
            ("today", "Today"),
            ("upcoming", "Upcoming"),
            ("completed", "Completed"),
        ],
        method="filter_tab",
    )

    def filter_tab(self, queryset, name, value):
        if value == "completed":
            return queryset.filter(status=Booking.BookingStatus.COMPLETED)
        active = queryset.exclude(
            status__in=[
                Booking.BookingStatus.COMPLETED,
                Booking.BookingStatus.CANCELLED,
                Booking.BookingStatus.EXPIRED,
            ]
        )
        today = timezone.localdate()
        if value == "today":
            return active.filter(scheduled_date=today)
        return active.filter(scheduled_date__gt=today)

    class Meta:
        model = Booking
        fields = ["status", "date", "booking_type", "tab"]
