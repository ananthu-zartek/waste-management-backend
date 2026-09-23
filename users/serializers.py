from phonenumber_field.serializerfields import PhoneNumberField
from rest_framework import serializers
from rest_framework_simplejwt.exceptions import TokenError
from rest_framework_simplejwt.tokens import RefreshToken

from .models import User

STATIC_OTP = "123456"


class UserSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ("id", "phone_number", "user_type", "created_at")


class OTPRequestSerializer(serializers.Serializer):
    phone_number = PhoneNumberField()
    user_type = serializers.ChoiceField(
        choices=User.UserType.choices,
        required=True,
        write_only=True,
    )


class VerifyOTPSerializer(serializers.Serializer):
    phone_number = PhoneNumberField()
    otp = serializers.CharField(write_only=True)

    def validate(self, attrs):
        if attrs["otp"] != STATIC_OTP:
            raise serializers.ValidationError({"otp": "Invalid OTP."})
        try:
            attrs["user"] = User.objects.get(phone_number=attrs["phone_number"])
        except User.DoesNotExist:
            raise serializers.ValidationError(
                {"phone_number": "No user exists with this phone number."}
            )
        return attrs


class AuthenticationResponseSerializer(serializers.Serializer):
    access = serializers.CharField()
    refresh = serializers.CharField()


class TokenRefreshSerializer(serializers.Serializer):
    refresh = serializers.CharField(write_only=True)

    def validate(self, attrs):
        try:
            attrs["token"] = RefreshToken(attrs["refresh"])
        except TokenError:
            raise serializers.ValidationError(
                {"refresh": "Invalid or expired refresh token."}
            )
        return attrs


class AccessTokenSerializer(serializers.Serializer):
    access = serializers.CharField(read_only=True)
