from rest_framework.viewsets import ModelViewSet
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import BasePermission, SAFE_METHODS
from django.utils import timezone
from rest_framework.exceptions import ValidationError

from bookings.services import eligible_drivers, slot_is_future
from bookings.capacity import SLOT_CAPACITY
from users.models import User

from .models import (
    WasteType,
    WasteCategory,
    WasteSubCategory,
    TimeSlot,
    ScrapMaterial,
)
from .serializers import (
    WasteTypeSerializer,
    WasteCategorySerializer,
    WasteSubCategorySerializer,
    TimeSlotSerializer,
    ScrapMaterialSerializer,
    SlotAvailabilityQuerySerializer,
)


class CatalogPermission(BasePermission):
    def has_permission(self, request, view):
        return request.user.is_authenticated and (
            request.method in SAFE_METHODS
            or request.user.user_type == User.UserType.ADMIN
        )


class ScrapMaterialViewSet(ModelViewSet):
    serializer_class = ScrapMaterialSerializer
    permission_classes = [CatalogPermission]

    def get_queryset(self):
        if self.request.user.user_type == User.UserType.ADMIN:
            return ScrapMaterial.objects.all()
        return ScrapMaterial.objects.filter(is_active=True)


class TimeSlotViewSet(ModelViewSet):
    permission_classes = [CatalogPermission]
    queryset = TimeSlot.objects.all()
    serializer_class = TimeSlotSerializer

    def list(self, request, *args, **kwargs):
        if "date" in request.query_params:
            return self.availability(request)
        return super().list(request, *args, **kwargs)

    @action(detail=False, methods=["get"])
    def availability(self, request):
        query = SlotAvailabilityQuerySerializer(data=request.query_params)
        query.is_valid(raise_exception=True)
        date = query.validated_data["date"]
        if date < timezone.localdate():
            raise ValidationError({"date": "Select today or a future date."})
        result = []
        for slot in TimeSlot.objects.filter(is_active=True):
            remaining = sum(
                SLOT_CAPACITY - driver.booking_count
                for driver in eligible_drivers(slot, date)
            )
            if not slot_is_future(slot, date):
                remaining = 0
            result.append(
                {
                    **TimeSlotSerializer(slot).data,
                    "date": date.isoformat(),
                    "is_available": remaining > 0,
                    "remaining_capacity": remaining,
                }
            )
        return Response(result)


class WasteTypeViewSet(ModelViewSet):
    permission_classes = [CatalogPermission]
    queryset = WasteType.objects.prefetch_related("categories__subcategories__category")
    serializer_class = WasteTypeSerializer


class WasteCategoryViewSet(ModelViewSet):
    permission_classes = [CatalogPermission]
    queryset = WasteCategory.objects.select_related("waste_type").prefetch_related(
        "subcategories__category"
    )
    serializer_class = WasteCategorySerializer


class WasteSubCategoryViewSet(ModelViewSet):
    permission_classes = [CatalogPermission]
    queryset = WasteSubCategory.objects.select_related(
        "category",
        "category__waste_type",
    )
    serializer_class = WasteSubCategorySerializer
