from rest_framework import serializers

from users.models import User
from users.serializers import UserSerializer

from .models import DriverProfile


class DriverProfileSerializer(serializers.ModelSerializer):
    user = UserSerializer(read_only=True)

    class Meta:
        model = DriverProfile
        fields = [
            "id",
            "user",
            "name",
            "email",
            "license_number",
            "vehicle_number",
            "is_available",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "created_at", "updated_at"]

    def validate_user(self, user):
        if user.user_type != User.UserType.DRIVER:
            raise serializers.ValidationError("The selected user must be a driver.")
        return user
