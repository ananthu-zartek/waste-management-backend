import json

from django.db import transaction
from rest_framework import status, viewsets
from rest_framework.renderers import JSONRenderer
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.exceptions import PermissionDenied, ValidationError
from django.core.exceptions import ValidationError as DjangoValidationError

from users.models import User
from customers.models import CustomerProfile
from .services import cancel_booking, confirm_booking, get_booking_request

from .models import (
    Booking,
    BookingWasteItem,
    ScrapBooking,
    ScrapBookingItem,
)
from .serializers import (
    BookingSerializer,
    BookingCreateSerializer,
    BookingCancelSerializer,
    BookingWasteItemSerializer,
    BookingWasteItemCreateSerializer,
    ScrapBookingSerializer,
    ScrapBookingItemSerializer,
    ScrapBookingItemCreateSerializer,
    ScrapQuoteSerializer,
)
from .scrap_services import quote_scrap
from . import waste_services, scrap_services


class BookingViewSet(viewsets.ModelViewSet):
    serializer_class = BookingSerializer
    http_method_names = ["get", "post", "patch", "head", "options"]

    def get_serializer_class(self):
        if self.action == "create":
            return BookingCreateSerializer
        return BookingSerializer

    @transaction.atomic
    def create(self, request, *args, **kwargs):
        user = request.user
        if user.user_type not in (User.UserType.ADMIN, User.UserType.CUSTOMER):
            raise PermissionDenied("Only customers and admins can create bookings.")
        key = request.headers.get("Idempotency-Key", "").strip()
        if not key or len(key) > 128:
            raise ValidationError(
                "Supply an Idempotency-Key header of 1 to 128 characters."
            )
        try:
            customer = user.customer_profile
        except CustomerProfile.DoesNotExist:
            raise ValidationError({"customer": "A customer profile is required."})
        attempt = get_booking_request(
            customer=customer, key=key, payload=request.data, role=user.user_type
        )
        if attempt.response is not None:
            return Response(attempt.response, status=status.HTTP_201_CREATED)
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        booking = serializer.save(
            customer=customer,
            source=(
                Booking.BookingSource.ADMIN
                if user.user_type == User.UserType.ADMIN
                else Booking.BookingSource.CUSTOMER
            ),
        )
        data = BookingSerializer(booking, context=self.get_serializer_context()).data
        attempt.booking = booking
        attempt.response = json.loads(JSONRenderer().render(data))
        attempt.save(update_fields=["booking", "response", "updated_at"])
        return Response(data, status=status.HTTP_201_CREATED)

    @action(detail=True, methods=["post"])
    def confirm(self, request, pk=None):
        if request.user.user_type != User.UserType.CUSTOMER:
            raise PermissionDenied("Only customers can confirm bookings.")
        booking = self.get_object()
        confirm_booking(booking_id=booking.pk, customer_id=booking.customer_id)
        return Response(self.get_serializer(self.get_object()).data)

    @action(detail=True, methods=["post"])
    def cancel(self, request, pk=None):
        booking = self.get_object()
        serializer = BookingCancelSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        cancel_booking(booking_id=booking.pk, **serializer.validated_data)
        return Response(self.get_serializer(self.get_object()).data)

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

    def get_queryset(self):
        queryset = Booking.objects.select_related(
            "customer",
            "customer__user",
            "driver",
            "driver__user",
            "address",
            "address__customer__user",
            "address__pincode",
            "slot",
            "scrap_booking",
        ).prefetch_related(
            "waste_items__subcategory__category",
            "scrap_booking__items__material",
        )
        user = self.request.user
        if user.user_type == User.UserType.ADMIN:
            return queryset
        if user.user_type == User.UserType.CUSTOMER:
            return queryset.filter(customer__user=user)
        if user.user_type == User.UserType.DRIVER and self.action in (
            "list",
            "retrieve",
        ):
            return queryset.filter(driver__user=user)
        return queryset.none()


class BookingWasteItemViewSet(viewsets.ModelViewSet):
    serializer_class = BookingWasteItemSerializer

    def get_serializer_class(self):
        if self.action == "create":
            return BookingWasteItemCreateSerializer
        return BookingWasteItemSerializer

    def perform_create(self, serializer):
        booking = serializer.validated_data["booking"]
        user = self.request.user
        if user.user_type != User.UserType.ADMIN and (
            user.user_type != User.UserType.CUSTOMER
            or booking.customer.user_id != user.pk
        ):
            raise PermissionDenied("You can only add items to your own bookings.")
        serializer.save()

    def perform_destroy(self, instance):
        waste_services.delete_item(instance)

    def get_queryset(self):
        queryset = BookingWasteItem.objects.select_related(
            "booking", "subcategory__category"
        )
        user = self.request.user
        if user.user_type == User.UserType.ADMIN:
            return queryset
        if user.user_type == User.UserType.CUSTOMER:
            return queryset.filter(booking__customer__user=user)
        return queryset.none()


class ScrapBookingViewSet(viewsets.ReadOnlyModelViewSet):
    serializer_class = ScrapBookingSerializer

    def get_queryset(self):
        queryset = ScrapBooking.objects.select_related("booking").prefetch_related(
            "items__material"
        )
        user = self.request.user
        if user.user_type == User.UserType.ADMIN:
            return queryset
        if user.user_type == User.UserType.CUSTOMER:
            return queryset.filter(booking__customer__user=user)
        return queryset.none()


class ScrapBookingItemViewSet(viewsets.ModelViewSet):
    serializer_class = ScrapBookingItemSerializer

    def get_serializer_class(self):
        if self.action == "create":
            return ScrapBookingItemCreateSerializer
        return ScrapBookingItemSerializer

    def perform_create(self, serializer):
        booking = serializer.validated_data["scrap_booking"].booking
        user = self.request.user
        if user.user_type != User.UserType.ADMIN and (
            user.user_type != User.UserType.CUSTOMER
            or booking.customer.user_id != user.pk
        ):
            raise PermissionDenied("You can only add items to your own bookings.")
        serializer.save()

    def perform_destroy(self, instance):
        scrap_services.delete_item(instance)

    def get_queryset(self):
        queryset = ScrapBookingItem.objects.select_related(
            "scrap_booking", "scrap_booking__booking", "material"
        )
        user = self.request.user
        if user.user_type == User.UserType.ADMIN:
            return queryset
        if user.user_type == User.UserType.CUSTOMER:
            return queryset.filter(scrap_booking__booking__customer__user=user)
        return queryset.none()
