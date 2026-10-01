from rest_framework import serializers
from catalog.models import ServicePincode
from bookings.models import Booking

from .models import Address, CustomerProfile
from users.serializers import UserSerializer


class CustomerProfileSerializer(serializers.ModelSerializer):
    user = UserSerializer(read_only=True)

    class Meta:
        model = CustomerProfile
        fields = ["id", "user", "name", "email"]


class AddressSerializer(serializers.ModelSerializer):
    user = UserSerializer(source="customer.user", read_only=True)
    pincode = serializers.PrimaryKeyRelatedField(queryset=ServicePincode.objects.all())

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
