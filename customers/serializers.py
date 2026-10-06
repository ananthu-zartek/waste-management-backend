from rest_framework import serializers
from catalog.models import ServicePincode
from bookings.models import Booking
from users.models import User
from .models import Address, CustomerProfile
from users.serializers import UserSerializer


class AddressSerializer(serializers.ModelSerializer):
    user = UserSerializer(source="customer.user", read_only=True)
    pincode = serializers.PrimaryKeyRelatedField(queryset=ServicePincode.objects.all())

    def create(self, validated_data):
        validated_data["customer"] = self.context["request"].user.customer_profile
        return super().create(validated_data)

    def validate_pincode(self, value):
        if not value.is_active or not value.service_area.is_active:
            raise serializers.ValidationError(
                "Service is not available for this pincode."
            )
        if self.instance and value != self.instance.pincode:
            if self.instance.bookings.exclude(
                status__in=[
                    Booking.BookingStatus.COMPLETED,
                    Booking.BookingStatus.CANCELLED,
                    Booking.BookingStatus.EXPIRED,
                ]
            ).exists():
                raise serializers.ValidationError(
                    "Cannot change the pincode while this address has active bookings."
                )
        return value

    class Meta:
        model = Address
        fields = [
            "id",
            "user",
            "address_type",
            "house_no",
            "area",
            "city",
            "pincode",
            "is_default",
        ]


class CustomerProfileSerializer(serializers.ModelSerializer):
    phone_number = serializers.CharField(
        source="user.phone_number",
        required=False,
    )
    is_active = serializers.BooleanField(source="user.is_active", required=False)
    current_address = AddressSerializer(read_only=True)
    completed_bookings_count = serializers.IntegerField(read_only=True)
    user_type = serializers.CharField(
        source="user.user_type",
        read_only=True,
    )
    created_at = serializers.DateTimeField(
        source="user.created_at",
        read_only=True,
    )

    class Meta:
        model = CustomerProfile
        fields = (
            "id",
            "phone_number",
            "user_type",
            "is_active",
            "current_address",
            "completed_bookings_count",
            "created_at",
            "name",
            "email",
        )
        read_only_fields = (
            "id",
            "user_type",
            "current_address",
            "completed_bookings_count",
            "created_at",
        )

    def validate_phone_number(self, phone_number):
        users = User.objects.filter(phone_number=phone_number)
        if self.instance:
            users = users.exclude(pk=self.instance.user_id)
        if users.exists():
            raise serializers.ValidationError("Phone number already exists.")
        return phone_number

    def update(self, instance, validated_data):
        user_data = validated_data.pop("user", None)
        if user_data:
            for field, value in user_data.items():
                setattr(instance.user, field, value)
            instance.user.save(update_fields=list(user_data))
        return super().update(instance, validated_data)
