from datetime import datetime, timedelta
from decimal import Decimal

from django.core.exceptions import ValidationError as DjangoValidationError
from django.db import transaction
from django.utils import timezone
from rest_framework import serializers

from catalog.models import ScrapMaterial, WasteSubCategory
from customers.mixins import CustomerProfileRequiredMixin
from customers.serializers import AddressSerializer, CustomerProfileSerializer
from drivers.models import DriverProfile
from drivers.serializers import DriverProfileSerializer
from catalog.serializers import WasteSubCategorySerializer
from users.models import User

from .models import (
    Booking,
    BookingWasteItem,
    ScrapBooking,
    ScrapBookingItem,
)
from . import services, waste_services, scrap_services
from .capacity import CONFIRMATION_WINDOW


class WasteItemInputSerializer(serializers.Serializer):
    subcategory = serializers.PrimaryKeyRelatedField(
        queryset=WasteSubCategory.objects.filter(is_active=True)
    )
    estimated_weight = serializers.DecimalField(
        max_digits=10, decimal_places=2, min_value=0
    )


class ScrapItemInputSerializer(serializers.Serializer):
    name = serializers.CharField(max_length=150, required=False)
    material = serializers.PrimaryKeyRelatedField(
        queryset=ScrapMaterial.objects.filter(is_active=True)
    )
    estimated_weight = serializers.DecimalField(
        max_digits=10, decimal_places=2, min_value=Decimal("0.01")
    )


class ScrapQuoteSerializer(serializers.Serializer):
    scrap_items = ScrapItemInputSerializer(many=True, allow_empty=False)


class BookingCreateSerializer(
    CustomerProfileRequiredMixin, serializers.ModelSerializer
):
    waste_items = WasteItemInputSerializer(many=True, required=False, write_only=True)
    scrap_items = ScrapItemInputSerializer(many=True, required=False, write_only=True)

    def validate(self, attrs):
        item_field = (
            "waste_items"
            if attrs.get("booking_type") == Booking.BookingType.WASTE
            else "scrap_items"
        )
        items = attrs.get(item_field, [])
        if items:
            configuration = self.get_customer_profile().system_configuration
            minimum_weight = (
                configuration.minimum_booking_weight
                if configuration
                else Decimal("5")
            )
            total_weight = sum(
                (item["estimated_weight"] for item in items), Decimal("0")
            )
            if total_weight < minimum_weight:
                raise serializers.ValidationError(
                    {item_field: f"Total estimated weight must be at least {minimum_weight} kg."}
                )
        return attrs

    class Meta:
        model = Booking
        fields = [
            "id",
            "customer",
            "driver",
            "address",
            "slot",
            "scheduled_date",
            "booking_type",
            "source",
            "status",
            "note",
            "waste_items",
            "scrap_items",
            "estimated_weight",
            "estimated_payout",
            "assigned_at",
            "confirmed_at",
            "completed_at",
            "cancelled_at",
            "expired_at",
            "created_at",
            "updated_at",
        ]
        read_only_fields = [
            "id",
            "customer",
            "source",
            "created_at",
            "updated_at",
            "assigned_at",
            "confirmed_at",
            "completed_at",
            "cancelled_at",
            "expired_at",
            "status",
            "driver",
            "estimated_payout",
        ]

    @transaction.atomic
    def create(self, validated_data):
        validated_data["customer"] = self.get_customer_profile()
        validated_data["source"] = Booking.BookingSource.CUSTOMER
        booking_type = validated_data.pop("booking_type")
        waste_items = validated_data.pop("waste_items", [])
        scrap_items = validated_data.pop("scrap_items", [])
        try:
            if booking_type == Booking.BookingType.WASTE:
                if scrap_items:
                    raise serializers.ValidationError(
                        "Waste bookings cannot contain scrap items."
                    )
                booking = waste_services.create_waste_booking(
                    waste_items=waste_items, **validated_data
                )
            else:
                if waste_items:
                    raise serializers.ValidationError(
                        "Scrap bookings cannot contain waste items."
                    )
                booking = scrap_services.create_scrap_booking(
                    scrap_items=scrap_items, **validated_data
                )
        except DjangoValidationError as exc:
            raise serializers.ValidationError(
                getattr(exc, "message_dict", exc.messages)
            )
        return booking


class BookingWasteItemSerializer(serializers.ModelSerializer):
    estimated_weight = serializers.DecimalField(
        max_digits=10, decimal_places=2, min_value=0
    )
    subcategory_details = WasteSubCategorySerializer(
        source="subcategory", read_only=True
    )

    class Meta:
        model = BookingWasteItem
        fields = [
            "id",
            "booking",
            "subcategory",
            "subcategory_details",
            "estimated_weight",
            "created_at",
        ]
        read_only_fields = ["id", "created_at", "booking"]

    @transaction.atomic
    def create(self, validated_data):
        return waste_services.add_item(**validated_data)

    @transaction.atomic
    def update(self, instance, validated_data):
        return waste_services.update_item(instance, **validated_data)


class BookingWasteItemCreateSerializer(BookingWasteItemSerializer):
    booking = serializers.PrimaryKeyRelatedField(
        queryset=Booking.objects.filter(booking_type=Booking.BookingType.WASTE)
    )

    class Meta(BookingWasteItemSerializer.Meta):
        read_only_fields = ["id", "created_at"]


class ScrapBookingItemSerializer(serializers.ModelSerializer):
    estimated_weight = serializers.DecimalField(
        max_digits=10, decimal_places=2, min_value=Decimal("0.01")
    )

    class Meta:
        model = ScrapBookingItem
        fields = [
            "id",
            "scrap_booking",
            "material",
            "name",
            "estimated_weight",
            "estimated_payout",
            "created_at",
        ]
        read_only_fields = [
            "id",
            "created_at",
            "estimated_payout",
            "scrap_booking",
            "material",
        ]

    @transaction.atomic
    def create(self, validated_data):
        return scrap_services.add_item(**validated_data)

    @transaction.atomic
    def update(self, instance, validated_data):
        return scrap_services.update_item(instance, **validated_data)


class ScrapBookingItemCreateSerializer(ScrapBookingItemSerializer):
    scrap_booking = serializers.PrimaryKeyRelatedField(
        queryset=ScrapBooking.objects.filter(
            booking__booking_type=Booking.BookingType.SCRAP
        )
    )

    class Meta(ScrapBookingItemSerializer.Meta):
        read_only_fields = ["id", "created_at", "estimated_payout"]


class ScrapBookingSerializer(serializers.ModelSerializer):
    items = ScrapBookingItemSerializer(many=True, read_only=True)

    class Meta:
        model = ScrapBooking
        fields = ["id", "booking", "items", "created_at", "updated_at"]
        read_only_fields = ["id", "created_at", "updated_at"]


class BookingSlotSerializer(serializers.Serializer):
    start_time = serializers.TimeField()
    end_time = serializers.TimeField()


class BookingSerializer(serializers.ModelSerializer):
    customer = CustomerProfileSerializer(read_only=True)
    driver = DriverProfileSerializer(read_only=True)
    driver_id = serializers.PrimaryKeyRelatedField(
        queryset=DriverProfile.objects.all(), write_only=True, required=False
    )
    previous_driver = serializers.PrimaryKeyRelatedField(read_only=True)
    reassigned_at = serializers.DateTimeField(read_only=True)
    address = AddressSerializer(read_only=True)
    waste_items = BookingWasteItemSerializer(many=True, read_only=True)
    scrap_items = ScrapBookingItemSerializer(
        source="scrap_booking.items", many=True, read_only=True, default=list
    )
    slot_details = BookingSlotSerializer(source="slot", read_only=True)
    reference = serializers.SerializerMethodField()
    cancelled_by = serializers.CharField(
        source="cancelled_by.user_type", read_only=True
    )

    def validate(self, attrs):
        instance = self.instance
        # Cancellation
        if (
            instance
            and attrs.get("status") == Booking.BookingStatus.CANCELLED
            and instance.status != Booking.BookingStatus.CANCELLED
        ):
            slot_start = timezone.make_aware(
                datetime.combine(instance.scheduled_date, instance.slot.start_time)
            )
            request = self.context.get("request")
            is_customer = (
                request is not None
                and getattr(request.user, "user_type", None) == User.UserType.CUSTOMER
            )
            cutoff_hours = 0
            if is_customer:
                system_configuration = instance.customer.system_configuration
                cutoff_hours = (
                    system_configuration.cancellation_cutoff_hours
                    if system_configuration
                    else 4
                )
            if timezone.now() >= slot_start - timedelta(hours=cutoff_hours):
                raise serializers.ValidationError(
                    {"status": "The cancellation deadline has passed."}
                )

        # Confirmation
        if (
            instance
            and attrs.get("status") == instance.BookingStatus.CONFIRMED
            and instance.status != instance.BookingStatus.CONFIRMED
        ):
            if timezone.now() >= instance.created_at + CONFIRMATION_WINDOW:
                raise serializers.ValidationError(
                    {"error": "Booking confirmation window has expired."}
                )

        return attrs

    @transaction.atomic
    def update(self, instance, validated_data):
        new_driver = validated_data.pop("driver_id", None)
        if new_driver is not None:
            try:
                return services.reassign_booking(
                    booking=instance, new_driver=new_driver
                )
            except DjangoValidationError as exc:
                raise serializers.ValidationError(
                    getattr(exc, "message_dict", exc.messages)
                ) from exc
        if (
            validated_data.get("status") == Booking.BookingStatus.CANCELLED
            and instance.status != Booking.BookingStatus.CANCELLED
        ):
            validated_data["cancelled_by"] = self.context["request"].user
        return super().update(instance, validated_data)

    class Meta:
        model = Booking
        fields = [
            # Identification
            "id",
            "reference",
            # Booking details
            "booking_type",
            "slot_details",
            "status",
            "source",
            "note",
            # Relationships
            "customer",
            "driver",
            "driver_id",
            "previous_driver",
            "address",
            "slot",
            # Schedule
            "scheduled_date",
            # Waste / Scrap
            "waste_items",
            "scrap_items",
            # Estimates
            "estimated_weight",
            "estimated_payout",
            # Cancellation
            "cancellation_notes",
            "cancelled_by",
            # Timestamps
            "created_at",
            "updated_at",
            "assigned_at",
            "reassigned_at",
            "confirmed_at",
            "completed_at",
            "cancelled_at",
            "expired_at",
        ]

    def get_reference(self, booking):
        return f"WKL-{booking.created_at.year}-{booking.pk:04d}"
