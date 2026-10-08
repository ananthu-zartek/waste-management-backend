from fcm_django.api.rest_framework import FCMDeviceAuthorizedViewSet
from rest_framework.routers import DefaultRouter

from .views import SystemConfigurationViewSet, UserViewSet

router = DefaultRouter()
router.register("auth", UserViewSet, basename="auth")
router.register(
    "system-configurations", SystemConfigurationViewSet, basename="system-configuration"
)
router.register("devices", FCMDeviceAuthorizedViewSet, basename="fcm-device")

urlpatterns = router.urls
