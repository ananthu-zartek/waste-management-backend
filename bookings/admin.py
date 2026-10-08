from django.contrib import admin
from django.db import transaction
from . import scrap_services

from .models import (
    Booking,
    BookingWasteItem,
    ScrapBookingItem,
)


@admin.register(Booking)
class BookingAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "customer",
        "driver",
        "address",
        "slot",
        "scheduled_date",
        "booking_type",
        "source",
        "status",
        "estimated_weight",
        "created_at",
    )
    list_filter = (
        "booking_type",
        "source",
        "status",
        "scheduled_date",
        "slot",
        "driver",
    )
    search_fields = (
        "customer__user__phone_number",
        "customer__email",
        "driver__user__phone_number",
        "driver__email",
    )
    autocomplete_fields = ("customer", "driver", "address", "slot")
    list_select_related = (
        "customer__user",
        "driver__user",
        "address__customer__user",
        "address__pincode",
        "slot",
    )


@admin.register(BookingWasteItem)
class BookingWasteItemAdmin(admin.ModelAdmin):
    list_display = ("id", "booking", "subcategory", "created_at")
    search_fields = ("=booking__id", "subcategory__name")
    autocomplete_fields = ("booking", "subcategory")
    list_select_related = ("booking__customer__user", "subcategory__category")

    def get_readonly_fields(self, request, obj=None):
        return ("booking",) if obj else ()


@admin.register(ScrapBookingItem)
class ScrapBookingItemAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "booking",
        "material",
        "name",
        "estimated_weight",
    )
    search_fields = ("material__name", "=booking__id")
    autocomplete_fields = ("booking", "material")
    list_select_related = ("booking", "material")

    def get_readonly_fields(self, request, obj=None):
        return (
            ("booking", "material", "estimated_payout")
            if obj
            else ("estimated_payout",)
        )

    def save_model(self, request, obj, form, change):
        data = {"name": obj.name, "estimated_weight": obj.estimated_weight}
        if change:
            scrap_services.update_item(obj, **data)
        else:
            obj.pk = scrap_services.add_item(
                booking=obj.booking, material=obj.material, **data
            ).pk

    def delete_model(self, request, obj):
        scrap_services.delete_item(obj)

    @transaction.atomic
    def delete_queryset(self, request, queryset):
        for item in queryset:
            scrap_services.delete_item(item)
