from fcm_django.api.rest_framework import FCMDeviceAuthorizedViewSet
from rest_framework.routers import DefaultRouter

from .views import UserViewSet

router = DefaultRouter()
router.register("auth", UserViewSet, basename="auth")
router.register("devices", FCMDeviceAuthorizedViewSet, basename="fcm-device")

urlpatterns = router.urls
