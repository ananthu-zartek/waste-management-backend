from rest_framework.routers import DefaultRouter

from .views import (
    WasteTypeViewSet,
    WasteCategoryViewSet,
    WasteSubCategoryViewSet,
    TimeSlotViewSet,
    ScrapMaterialViewSet,
)

router = DefaultRouter()
router.register("scrap-materials", ScrapMaterialViewSet, basename="scrap-material")
router.register("time-slots", TimeSlotViewSet, basename="time-slot")
router.register("waste-types", WasteTypeViewSet, basename="waste-type")
router.register("waste-categories", WasteCategoryViewSet, basename="waste-category")
router.register(
    "waste-subcategories", WasteSubCategoryViewSet, basename="waste-subcategory"
)
urlpatterns = router.urls
