from rest_framework.routers import DefaultRouter

from .views import (
    BookingViewSet,
    BookingWasteItemViewSet,
    ScrapBookingViewSet,
    ScrapBookingItemViewSet,
)

router = DefaultRouter()
router.register("bookings", BookingViewSet, basename="booking")
router.register(
    "booking-waste-items", BookingWasteItemViewSet, basename="booking-waste-item"
)
router.register("scrap-bookings", ScrapBookingViewSet, basename="scrap-booking")
router.register(
    "scrap-booking-items", ScrapBookingItemViewSet, basename="scrap-booking-item"
)
urlpatterns = router.urls
