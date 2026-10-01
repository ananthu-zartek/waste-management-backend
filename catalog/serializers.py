from rest_framework import serializers
from django.core.exceptions import ValidationError as DjangoValidationError
from django.db import transaction
from django.utils import timezone
from .services import validate_service_pincode

from .models import (
    WasteType,
    WasteCategory,
    WasteSubCategory,
    TimeSlot,
    ScrapMaterial,
    ServiceArea,
    ServicePincode,
)


class ServicePincodeSerializer(serializers.ModelSerializer):
    class Meta:
        model = ServicePincode
        fields = ["id", "service_area", "pincode", "area_name", "is_active"]
        read_only_fields = ["id"]


class ServiceAreaSerializer(serializers.ModelSerializer):
    pincodes = ServicePincodeSerializer(many=True, read_only=True)

    class Meta:
        model = ServiceArea
        fields = ["id", "name", "is_active", "pincodes"]
        read_only_fields = ["id"]


class ScrapMaterialSerializer(serializers.ModelSerializer):
    class Meta:
        model = ScrapMaterial
        fields = ["id", "name", "price_per_kg", "is_active"]
        read_only_fields = ["id"]


class SlotAvailabilityQuerySerializer(serializers.Serializer):
    date = serializers.DateField(
        error_messages={
            "invalid": "Invalid date. Please provide a valid calendar date."
        }
    )
    pincode = serializers.CharField(max_length=6)

    def validate_date(self, value):
        if value < timezone.localdate():
            raise serializers.ValidationError("Select today or a future date.")
        return value

    def validate(self, attrs):
        try:
            validate_service_pincode(attrs["pincode"])
        except DjangoValidationError as exc:
            raise serializers.ValidationError(exc.message_dict) from exc
        return attrs


class TimeSlotSerializer(serializers.ModelSerializer):
    class Meta:
        model = TimeSlot
        fields = [
            "id",
            "start_time",
            "end_time",
            "is_active",
        ]
        read_only_fields = ["id"]

    def validate(self, attrs):
        start_time = attrs.get("start_time")
        end_time = attrs.get("end_time")
        if start_time and end_time and start_time >= end_time:
            raise serializers.ValidationError(
                {"end_time": "End time must be after start time."}
            )

        return attrs


class WasteSubCategorySerializer(serializers.ModelSerializer):
    class Meta:
        model = WasteSubCategory
        fields = [
            "id",
            "category",
            "name",
            "is_active",
        ]
        read_only_fields = ["id"]


class NestedWasteSubCategorySerializer(WasteSubCategorySerializer):
    category = serializers.PrimaryKeyRelatedField(read_only=True)


class WasteCategorySerializer(serializers.ModelSerializer):
    subcategories = NestedWasteSubCategorySerializer(many=True, required=False)

    class Meta:
        model = WasteCategory
        fields = [
            "id",
            "waste_type",
            "name",
            "description",
            "price_per_kg",
            "is_active",
            "subcategories",
        ]
        read_only_fields = ["id"]

    def validate_subcategories(self, value):
        names = [item["name"] for item in value]
        if len(names) != len(set(names)):
            raise serializers.ValidationError("Subcategory names must be unique.")
        return value

    @transaction.atomic
    def create(self, validated_data):
        subcategories = validated_data.pop("subcategories", [])
        category = WasteCategory.objects.create(**validated_data)
        for subcategory in subcategories:
            WasteSubCategory.objects.create(category=category, **subcategory)
        return category


class WasteTypeSerializer(serializers.ModelSerializer):
    categories = WasteCategorySerializer(
        many=True,
        read_only=True,
    )

    class Meta:
        model = WasteType
        fields = [
            "id",
            "name",
            "is_active",
            "categories",
        ]
        read_only_fields = ["id"]
