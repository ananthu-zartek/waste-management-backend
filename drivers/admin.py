from django.contrib import admin

from .models import DriverProfile, DriverSlot


@admin.register(DriverProfile)
class DriverProfileAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "user",
        "license_number",
        "vehicle_number",
        "is_available",
        "created_at",
    )
    list_filter = ("is_available",)
    search_fields = ("user__phone_number", "email", "license_number", "vehicle_number")
    autocomplete_fields = ("user", "service_pincodes")
    ordering = ("id",)


@admin.register(DriverSlot)
class DriverSlotAdmin(admin.ModelAdmin):
    list_display = ("id", "driver", "slot", "date", "booking", "created_at")
    list_filter = ("driver", "slot", "date")
    search_fields = (
        "driver__user__phone_number",
        "driver__email",
        "driver__vehicle_number",
        "=booking__id",
    )
    autocomplete_fields = ("driver", "slot", "booking")

    def get_queryset(self, request):
        return (
            super()
            .get_queryset(request)
            .select_related(
                "driver", "driver__user", "slot", "booking", "booking__customer__user"
            )
        )
