from django.db import transaction
from phonenumber_field.serializerfields import PhoneNumberField
from rest_framework import serializers
from catalog.models import ServicePincode
from catalog.serializers import ServicePincodeSerializer

from users.models import User
from .models import DriverProfile


class DriverProfileSerializer(serializers.ModelSerializer):
    phone_number = PhoneNumberField(source="user.phone_number", required=True)
    user_type = serializers.CharField(source="user.user_type", read_only=True)
    user_id = serializers.IntegerField(read_only=True)
    service_pincodes = serializers.PrimaryKeyRelatedField(
        many=True,
        required=False,
        queryset=ServicePincode.objects.filter(
            is_active=True,
            service_area__is_active=True,
        ),
        write_only=True,
    )
    service_pincode_details = ServicePincodeSerializer(
        source="service_pincodes",
        many=True,
        read_only=True,
    )

    class Meta:
        model = DriverProfile
        fields = [
            "id",
            "phone_number",
            "user_type",
            "user_id",
            "name",
            "email",
            "license_number",
            "vehicle_number",
            "is_available",
            "service_pincodes",
            "service_pincode_details",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "user_type", "created_at", "updated_at"]

    def validate_phone_number(self, phone_number):
        users = User.objects.filter(phone_number=phone_number)
        if self.instance:
            users = users.exclude(pk=self.instance.user_id)
        if users.exists():
            raise serializers.ValidationError(
                "A user with this phone number already exists."
            )
        return phone_number

    @transaction.atomic
    def create(self, validated_data):
        phone_number = validated_data.pop("user")["phone_number"]
        pincodes = validated_data.pop("service_pincodes", [])
        user = User.objects.create_user(
            phone_number=phone_number, user_type=User.UserType.DRIVER
        )
        driver = DriverProfile.objects.create(user=user, **validated_data)
        driver.service_pincodes.set(pincodes)
        return driver

    @transaction.atomic
    def update(self, instance, validated_data):
        instance = DriverProfile.objects.select_for_update().get(pk=instance.pk)
        user_data = validated_data.pop("user", None)
        if user_data:
            User.objects.filter(pk=instance.user_id).update(**user_data)
        return super().update(instance, validated_data)
