from rest_framework import viewsets
from rest_framework.decorators import action
from rest_framework.response import Response
from django.db.models import Count

from bookings.models import Booking
from drivers.models import DriverProfile
from .services import CAPACITY_STATUSES

from .models import (
    QuickAction,
    WasteType,
    WasteCategory,
    WasteSubCategory,
    TimeSlot,
    ScrapMaterial,
    ServiceArea,
    ServicePincode,
)
from .serializers import (
    QuickActionSerializer,
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


class QuickActionViewSet(viewsets.ModelViewSet):
    queryset = QuickAction.objects.all()
    serializer_class = QuickActionSerializer


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
        future_slots = [
            slot for slot in slots if slot.is_service_day(date) and slot.slot_is_future(date)
        ]
        remaining_by_slot = {}
        if future_slots:
            eligible = DriverProfile.drivers_serving_pincode(
                query.validated_data["pincode"]
            )
            if eligible.exists():
                remaining_by_slot = {
                    slot.pk: slot.capacity for slot in future_slots
                }
                reservations = (
                    Booking.objects.filter(
                        scheduled_date=date,
                        slot__in=future_slots,
                        status__in=CAPACITY_STATUSES,
                    )
                    .values("slot_id")
                    .annotate(count=Count("pk"))
                )
                for row in reservations:
                    remaining_by_slot[row["slot_id"]] = max(
                        0, remaining_by_slot[row["slot_id"]] - row["count"]
                    )
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
