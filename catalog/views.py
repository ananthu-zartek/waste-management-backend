from rest_framework import viewsets
from rest_framework.decorators import action
from rest_framework.response import Response
from django.db.models import Count

from bookings.services import drivers_serving_pincode, slot_is_future
from bookings.capacity import SLOT_CAPACITY
from drivers.models import DriverSlot

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


class ServiceAreaViewSet(viewsets.ModelViewSet):
    queryset = ServiceArea.objects.prefetch_related("pincodes")
    serializer_class = ServiceAreaSerializer
    filterset_fields = ["is_active"]


class ServicePincodeViewSet(viewsets.ModelViewSet):
    queryset = ServicePincode.objects.select_related("service_area")
    serializer_class = ServicePincodeSerializer
    filterset_fields = ["service_area", "is_active"]


class ScrapMaterialViewSet(viewsets.ModelViewSet):
    queryset = ScrapMaterial.objects.all()
    serializer_class = ScrapMaterialSerializer


class TimeSlotViewSet(viewsets.ModelViewSet):
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
        slots = list(TimeSlot.objects.filter(is_active=True))
        future_slots = [slot for slot in slots if slot_is_future(slot, date)]
        remaining_by_slot = {}
        if future_slots:
            eligible = drivers_serving_pincode(query.validated_data["pincode"])
            driver_count = eligible.count()
            if driver_count:
                remaining_by_slot = {
                    slot.pk: driver_count * SLOT_CAPACITY for slot in future_slots
                }
                reservations = (
                    DriverSlot.objects.filter(
                        date=date,
                        slot__in=future_slots,
                        driver_id__in=eligible.values("pk"),
                    )
                    .values("slot_id")
                    .annotate(count=Count("pk"))
                )
                for row in reservations:
                    remaining_by_slot[row["slot_id"]] -= row["count"]
        result = []
        for slot in slots:
            remaining = remaining_by_slot.get(slot.pk, 0)
            result.append(
                {
                    **TimeSlotSerializer(slot).data,
                    "date": date.isoformat(),
                    "is_available": remaining > 0,
                    "remaining_capacity": remaining,
                }
            )
        return Response(result)


class WasteTypeViewSet(viewsets.ModelViewSet):
    queryset = WasteType.objects.prefetch_related("categories__subcategories__category")
    serializer_class = WasteTypeSerializer


class WasteCategoryViewSet(viewsets.ModelViewSet):
    queryset = (
        WasteCategory.objects.select_related("waste_type")
        .prefetch_related("subcategories__category")
        .order_by("id")
    )
    serializer_class = WasteCategorySerializer


class WasteSubCategoryViewSet(viewsets.ModelViewSet):
    queryset = WasteSubCategory.objects.select_related(
        "category",
        "category__waste_type",
    )
    serializer_class = WasteSubCategorySerializer
