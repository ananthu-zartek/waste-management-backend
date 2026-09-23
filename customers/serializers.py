from rest_framework import serializers

from .models import Address, CustomerProfile
from users.serializers import UserSerializer


class CustomerProfileSerializer(serializers.ModelSerializer):
    user = UserSerializer(read_only=True)

    class Meta:
        model = CustomerProfile
        fields = ["id", "user", "name", "email"]


class AddressSerializer(serializers.ModelSerializer):
    user = UserSerializer(source="customer.user", read_only=True)

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
