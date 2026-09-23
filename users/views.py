from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import PermissionDenied
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework_simplejwt.tokens import RefreshToken

from .models import User
from .serializers import (
    STATIC_OTP,
    AccessTokenSerializer,
    AuthenticationResponseSerializer,
    OTPRequestSerializer,
    TokenRefreshSerializer,
    VerifyOTPSerializer,
)


class UserViewSet(viewsets.ModelViewSet):
    queryset = User.objects.all()
    serializer_class = OTPRequestSerializer
    permission_classes = [AllowAny]
    http_method_names = ["post", "options", "head"]
    serializer_action_classes = {
        "verify_otp": VerifyOTPSerializer,
        "token_refresh": TokenRefreshSerializer,
    }

    def get_serializer_class(self):
        return self.serializer_action_classes.get(
            self.action, super().get_serializer_class()
        )

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        phone_number = serializer.validated_data["phone_number"]
        user_type = serializer.validated_data["user_type"]
        _, created = User.objects.get_or_create(
            phone_number=phone_number,
            defaults={
                "user_type": user_type,
            },
        )
        response_status = status.HTTP_201_CREATED if created else status.HTTP_200_OK
        return Response(
            {"detail": "OTP Sent.", "otp": STATIC_OTP},
            status=response_status,
        )

    @action(
        detail=False,
        methods=["post"],
        permission_classes=[AllowAny],
        url_path="verify-otp",
    )
    def verify_otp(self, request):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = serializer.validated_data["user"]
        if not user.is_active:
            raise PermissionDenied("This account is inactive.")
        refresh = RefreshToken.for_user(user)
        response_data = {
            "access": str(refresh.access_token),
            "refresh": str(refresh),
        }
        return Response(AuthenticationResponseSerializer(response_data).data)

    @action(
        detail=False,
        methods=["post"],
        permission_classes=[AllowAny],
        url_path="token-refresh",
    )
    def token_refresh(self, request):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        response = AccessTokenSerializer(
            {"access": str(serializer.validated_data["token"].access_token)}
        )
        return Response(response.data)
