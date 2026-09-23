from rest_framework import serializers

from .models import (
    WasteType,
    WasteCategory,
    WasteSubCategory,
    TimeSlot,
    ScrapMaterial,
)


class ScrapMaterialSerializer(serializers.ModelSerializer):
    class Meta:
        model = ScrapMaterial
        fields = ["id", "name", "price_per_kg", "is_active"]
        read_only_fields = ["id"]


class SlotAvailabilityQuerySerializer(serializers.Serializer):
    date = serializers.DateField()


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
    price_per_kg = serializers.DecimalField(
        source="category.price_per_kg", max_digits=10, decimal_places=2, read_only=True
    )

    class Meta:
        model = WasteSubCategory
        fields = [
            "id",
            "category",
            "name",
            "price_per_kg",
            "is_active",
        ]
        read_only_fields = ["id"]


class WasteCategorySerializer(serializers.ModelSerializer):
    subcategories = WasteSubCategorySerializer(
        many=True,
        read_only=True,
    )

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
