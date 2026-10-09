from decimal import Decimal

from django.core.exceptions import ObjectDoesNotExist
from django.db import transaction
from rest_framework import serializers

from catalog.models import ScrapMaterial, WasteSubCategory
from catalog.serializers import WasteSubCategorySerializer
from customers.serializers import AddressSerializer, CustomerProfileSerializer
from drivers.models import DriverProfile
from drivers.serializers import DriverProfileSerializer
from users.models import SystemConfiguration, User

from . import scrap_services, services, waste_services
from .models import Booking, BookingWasteItem, ScrapBookingItem


class WasteItemInputSerializer(serializers.Serializer):
    subcategory = serializers.PrimaryKeyRelatedField(
        queryset=WasteSubCategory.objects.filter(is_active=True)
    )


class ScrapItemInputSerializer(serializers.Serializer):
    material = serializers.PrimaryKeyRelatedField(
        queryset=ScrapMaterial.objects.filter(is_active=True)
    )
    estimated_weight = serializers.DecimalField(
        max_digits=10, decimal_places=2, min_value=Decimal("0.01")
    )


class ScrapQuoteSerializer(serializers.Serializer):
    scrap_items = ScrapItemInputSerializer(many=True, allow_empty=False)


class BookingCreateSerializer(serializers.ModelSerializer):
    waste_items = WasteItemInputSerializer(many=True, required=False, write_only=True)
    scrap_items = ScrapItemInputSerializer(many=True, required=False, write_only=True)

    def validate(self, attrs):
        try:
            self.context["request"].user.customer_profile
        except ObjectDoesNotExist:
            raise serializers.ValidationError({"error": "Customer profile not found."})

        config = SystemConfiguration.objects.first()
        minimum_weight = config.minimum_booking_weight if config else Decimal("5")
        booking_type = attrs.get("booking_type")
        is_waste = booking_type == Booking.BookingType.WASTE
        item_field = "waste_items" if is_waste else "scrap_items"
        items = attrs.get(item_field, [])

        if not items:
            return attrs

        if is_waste:
            total_weight = attrs.get("estimated_weight", Decimal("0"))
            error_field = "estimated_weight"
        else:
            total_weight = sum(
                (item["estimated_weight"] for item in items),
                Decimal("0"),
            )
            error_field = item_field

        if total_weight < minimum_weight:
            raise serializers.ValidationError(
                {error_field: f"Minimum weight must be at least {minimum_weight} kg."}
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
        validated_data["customer"] = self.context["request"].user.customer_profile
        booking_type = validated_data.pop("booking_type")
        waste_items = validated_data.pop("waste_items", [])
        scrap_items = validated_data.pop("scrap_items", [])
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
        return booking


class BookingWasteItemSerializer(serializers.ModelSerializer):
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
            "created_at",
        ]
        read_only_fields = ["id", "created_at", "booking"]


class BookingWasteItemCreateSerializer(BookingWasteItemSerializer):
    booking = serializers.PrimaryKeyRelatedField(
        queryset=Booking.objects.filter(booking_type=Booking.BookingType.WASTE)
    )

    class Meta(BookingWasteItemSerializer.Meta):
        read_only_fields = ["id", "created_at"]


class ScrapBookingItemSerializer(serializers.ModelSerializer):
    name = serializers.CharField(source="material.name", read_only=True)
    estimated_weight = serializers.DecimalField(
        max_digits=10, decimal_places=2, min_value=Decimal("0.01")
    )

    class Meta:
        model = ScrapBookingItem
        fields = [
            "id",
            "booking",
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
            "booking",
            "material",
        ]

    @transaction.atomic
    def create(self, validated_data):
        return scrap_services.add_item(**validated_data)

    @transaction.atomic
    def update(self, instance, validated_data):
        return scrap_services.update_item(instance, **validated_data)


class ScrapBookingItemCreateSerializer(ScrapBookingItemSerializer):
    booking = serializers.PrimaryKeyRelatedField(
        queryset=Booking.objects.filter(booking_type=Booking.BookingType.SCRAP)
    )

    class Meta(ScrapBookingItemSerializer.Meta):
        read_only_fields = ["id", "created_at", "estimated_payout"]


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
    scrap_items = ScrapBookingItemSerializer(many=True, read_only=True)
    slot_details = BookingSlotSerializer(source="slot", read_only=True)
    reference = serializers.SerializerMethodField()
    cancelled_by = serializers.PrimaryKeyRelatedField(
        queryset=User.objects.all(), required=False, allow_null=True
    )
    cancelled_by_type = serializers.CharField(
        source="cancelled_by.user_type", read_only=True
    )

    def validate(self, attrs):
        request = self.context.get("request")
        services.validate_booking(
            self.instance,
            attrs.get("status"),
            request.user if request is not None else None,
        )
        return attrs

    @transaction.atomic
    def update(self, instance, validated_data):
        new_driver = validated_data.pop("driver_id", None)
        if new_driver is not None:
            return services.reassign_booking(booking=instance, new_driver=new_driver)

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
            "cancelled_by_type",
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
