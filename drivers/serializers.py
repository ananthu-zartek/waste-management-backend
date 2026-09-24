from django.db import transaction
from phonenumber_field.serializerfields import PhoneNumberField
from rest_framework import serializers
from catalog.models import ServicePincode

from users.models import User
from users.serializers import UserSerializer

from .models import DriverProfile


class DriverProfileSerializer(serializers.ModelSerializer):
    user = UserSerializer(read_only=True)
    phone_number = PhoneNumberField(write_only=True, required=True)
    service_pincodes = serializers.SlugRelatedField(
        many=True,
        slug_field="pincode",
        required=False,
        queryset=ServicePincode.objects.filter(
            is_active=True, service_area__is_active=True
        ),
    )

    class Meta:
        model = DriverProfile
        fields = [
            "id",
            "user",
            "phone_number",
            "name",
            "email",
            "license_number",
            "vehicle_number",
            "is_available",
            "service_pincodes",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "created_at", "updated_at"]

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
        phone_number = validated_data.pop("phone_number")
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
        phone_number = validated_data.pop("phone_number", None)
        if phone_number is not None:
            instance.user.phone_number = phone_number
            instance.user.save(update_fields=["phone_number"])
        return super().update(instance, validated_data)
