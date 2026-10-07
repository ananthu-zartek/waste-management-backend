from django.core.exceptions import ValidationError as DjangoValidationError
from django.db import transaction
from django.db.models import CharField
from django.db.models.functions import Cast
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework import viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import ValidationError
from rest_framework.filters import SearchFilter
from rest_framework.response import Response


from . import scrap_services
from .filters import BookingFilter
from .mixins import UserScopedQuerysetMixin
from .models import Booking, BookingWasteItem, ScrapBooking, ScrapBookingItem
from .scrap_services import quote_scrap
from .serializers import (
    BookingCreateSerializer,
    BookingSerializer,
    BookingWasteItemCreateSerializer,
    BookingWasteItemSerializer,
    ScrapBookingItemCreateSerializer,
    ScrapBookingItemSerializer,
    ScrapBookingSerializer,
    ScrapQuoteSerializer,
)


class BookingViewSet(UserScopedQuerysetMixin, viewsets.ModelViewSet):
    queryset = (
        Booking.objects.select_related(
            "customer",
            "customer__user",
            "driver",
            "driver__user",
            "cancelled_by",
            "address",
            "address__customer__user",
            "address__pincode",
            "slot",
            "scrap_booking",
        )
        .prefetch_related(
            "waste_items__subcategory__category",
            "scrap_booking__items__material",
        )
        .annotate(search_id=Cast("id", output_field=CharField()))
        .order_by("scheduled_date", "slot__start_time", "pk")
    )
    customer_lookup = "customer__user"
    driver_lookup = "driver__user"
    serializer_class = BookingSerializer
    filter_backends = [DjangoFilterBackend, SearchFilter]
    filterset_class = BookingFilter
    search_fields = [
        "note",
        "customer__name",
        "customer__user__phone_number",
        "address__house_no",
        "address__area",
        "address__city",
        "search_id",
    ]
    http_method_names = ["get", "post", "patch", "head", "options"]

    def filter_queryset(self, queryset):
        if self.action == "list":
            return super().filter_queryset(queryset)
        return queryset

    def get_serializer_class(self):
        if self.action == "create":
            return BookingCreateSerializer
        return BookingSerializer

    @action(detail=False, methods=["post"])
    def quote(self, request):
        serializer = ScrapQuoteSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            items = quote_scrap(serializer.validated_data["scrap_items"])
        except DjangoValidationError as exc:
            raise ValidationError(getattr(exc, "message_dict", exc.messages))
        return Response(
            {
                "items": [
                    {
                        **item,
                        "material": item["material"].pk,
                        "estimated_weight": str(item["estimated_weight"]),
                        "price_per_kg": str(item["price_per_kg"]),
                        "estimated_payout": str(item["estimated_payout"]),
                    }
                    for item in items
                ],
                "estimated_payout": str(
                    sum(item["estimated_payout"] for item in items)
                ),
            }
        )


class BookingWasteItemViewSet(UserScopedQuerysetMixin, viewsets.ModelViewSet):
    queryset = BookingWasteItem.objects.select_related(
        "booking", "subcategory__category"
    )
    customer_lookup = "booking__customer__user"
    serializer_class = BookingWasteItemSerializer

    def get_serializer_class(self):
        if self.action == "create":
            return BookingWasteItemCreateSerializer
        return BookingWasteItemSerializer


class ScrapBookingViewSet(UserScopedQuerysetMixin, viewsets.ReadOnlyModelViewSet):
    queryset = ScrapBooking.objects.select_related("booking").prefetch_related(
        "items__material"
    )
    customer_lookup = "booking__customer__user"
    serializer_class = ScrapBookingSerializer


class ScrapBookingItemViewSet(UserScopedQuerysetMixin, viewsets.ModelViewSet):
    queryset = ScrapBookingItem.objects.select_related(
        "scrap_booking", "scrap_booking__booking", "material"
    )
    customer_lookup = "scrap_booking__booking__customer__user"
    serializer_class = ScrapBookingItemSerializer

    def get_serializer_class(self):
        if self.action == "create":
            return ScrapBookingItemCreateSerializer
        return ScrapBookingItemSerializer

    @transaction.atomic
    def perform_destroy(self, instance):
        scrap_services.delete_item(instance)
