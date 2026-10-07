from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import PermissionDenied
from rest_framework.response import Response
from rest_framework_simplejwt.tokens import RefreshToken
from config.permission_mixins import AllowAnyMixin

from .models import User
from .serializers import (
    STATIC_OTP,
    AccessTokenSerializer,
    AuthenticationResponseSerializer,
    OTPRequestSerializer,
    TokenRefreshSerializer,
    VerifyOTPSerializer,
)


class UserViewSet(AllowAnyMixin, viewsets.ModelViewSet):
    queryset = User.objects.all()
    serializer_class = OTPRequestSerializer
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
        serializer.save()
        response_status = (
            status.HTTP_201_CREATED if serializer.created else status.HTTP_200_OK
        )
        return Response(
            {"detail": "OTP Sent.", "otp": STATIC_OTP},
            status=response_status,
        )

    @action(
        detail=False,
        methods=["post"],
        url_path="verify-otp",
    )
    def verify_otp(self, request):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = serializer.validated_data["user"]
        refresh = RefreshToken.for_user(user)
        response_data = {
            "access": str(refresh.access_token),
            "refresh": str(refresh),
            "user_type": user.user_type,
        }
        return Response(AuthenticationResponseSerializer(response_data).data)

    @action(
        detail=False,
        methods=["post"],
        url_path="token-refresh",
    )
    def token_refresh(self, request):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        response = AccessTokenSerializer(
            {"access": str(serializer.validated_data["token"].access_token)}
        )
        return Response(response.data)
