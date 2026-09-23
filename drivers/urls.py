from rest_framework.routers import DefaultRouter

from .views import DriverProfileViewSet

router = DefaultRouter()
router.register("drivers", DriverProfileViewSet, basename="driver")
urlpatterns = router.urls
