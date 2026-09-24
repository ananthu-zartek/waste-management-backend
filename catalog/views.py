from rest_framework.viewsets import ModelViewSet
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import BasePermission, SAFE_METHODS
from django.utils import timezone
from django.db.models import Prefetch
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
    ServiceArea,
    ServicePincode,
)
from .serializers import (
    WasteTypeSerializer,
    WasteCategorySerializer,
    WasteSubCategorySerializer,
    TimeSlotSerializer,
    ScrapMaterialSerializer,
    SlotAvailabilityQuerySerializer,
    ServiceAreaSerializer,
    ServicePincodeSerializer,
)


class CatalogPermission(BasePermission):
    def has_permission(self, request, view):
        return request.user.is_authenticated and (
            request.method in SAFE_METHODS
            or request.user.user_type == User.UserType.ADMIN
        )


class ServiceAreaViewSet(ModelViewSet):
    permission_classes = [CatalogPermission]
    serializer_class = ServiceAreaSerializer
    http_method_names = ["get", "post", "put", "patch", "head", "options"]

    def get_queryset(self):
        areas = ServiceArea.objects.all()
        pincodes = ServicePincode.objects.all()
        if self.request.user.user_type != User.UserType.ADMIN:
            areas = areas.filter(is_active=True)
            pincodes = pincodes.filter(is_active=True)
        return areas.prefetch_related(Prefetch("pincodes", queryset=pincodes))


class ServicePincodeViewSet(ModelViewSet):
    permission_classes = [CatalogPermission]
    serializer_class = ServicePincodeSerializer
    http_method_names = ["get", "post", "put", "patch", "head", "options"]

    def get_queryset(self):
        queryset = ServicePincode.objects.select_related("service_area")
        if self.request.user.user_type != User.UserType.ADMIN:
            queryset = queryset.filter(is_active=True, service_area__is_active=True)
        area_id = self.request.query_params.get("service_area")
        if area_id is not None:
            if not area_id.isascii() or not area_id.isdigit():
                raise ValidationError(
                    {"service_area": "Select a valid service area ID."}
                )
            queryset = queryset.filter(service_area_id=area_id)
        return queryset


class ScrapMaterialViewSet(ModelViewSet):
    serializer_class = ScrapMaterialSerializer
    # permission_classes = [CatalogPermission]

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
        if date < timezone.now().date():
            raise ValidationError({"date": "Select today or a future date."})
        result = []
        for slot in TimeSlot.objects.filter(is_active=True):
            remaining = sum(
                SLOT_CAPACITY - driver.booking_count
                for driver in eligible_drivers(
                    slot, date, query.validated_data["pincode"]
                )
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
