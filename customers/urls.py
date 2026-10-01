from rest_framework.routers import DefaultRouter

from .views import CustomerProfileViewSet, AddressViewSet

router = DefaultRouter()
router.register("addresses", AddressViewSet, basename="address")
router.register("profiles", CustomerProfileViewSet, basename="profiles")
urlpatterns = router.urls
