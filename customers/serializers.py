from rest_framework import serializers
from django.core.exceptions import ValidationError as DjangoValidationError
from catalog.services import validate_service_pincode
from catalog.models import ServicePincode

from .models import Address, CustomerProfile
from users.serializers import UserSerializer


class CustomerProfileSerializer(serializers.ModelSerializer):
    user = UserSerializer(read_only=True)

    class Meta:
        model = CustomerProfile
        fields = ["id", "user", "name", "email"]


class AddressSerializer(serializers.ModelSerializer):
    user = UserSerializer(source="customer.user", read_only=True)
    pincode = serializers.SlugRelatedField(
        slug_field="pincode",
        queryset=ServicePincode.objects.filter(
            is_active=True, service_area__is_active=True
        ),
    )

    def validate(self, attrs):
        pincode = attrs.get("pincode", self.instance.pincode if self.instance else None)
        if pincode is not None:
            try:
                validate_service_pincode(pincode.pincode)
            except DjangoValidationError as exc:
                raise serializers.ValidationError(exc.message_dict) from exc
        if (
            self.instance
            and "pincode" in attrs
            and attrs["pincode"] != self.instance.pincode
        ):
            from bookings.models import Booking

            if self.instance.bookings.exclude(
                status__in=[
                    Booking.BookingStatus.COMPLETED,
                    Booking.BookingStatus.CANCELLED,
                    Booking.BookingStatus.EXPIRED,
                ]
            ).exists():
                raise serializers.ValidationError(
                    {
                        "pincode": "Cannot change the pincode while this address has active bookings."
                    }
                )
        return attrs

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
        ]
