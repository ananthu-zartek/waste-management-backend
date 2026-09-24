from django.contrib import admin

from .models import WasteType, WasteCategory, WasteSubCategory, TimeSlot
from .models import ScrapMaterial
from .models import ServiceArea, ServicePincode


class ServicePincodeInline(admin.TabularInline):
    model = ServicePincode
    extra = 1
    can_delete = True
    show_change_link = True


@admin.register(ServiceArea)
class ServiceAreaAdmin(admin.ModelAdmin):
    list_display = ("name", "is_active")
    list_filter = ("is_active",)
    search_fields = ("name",)
    inlines = (ServicePincodeInline,)


@admin.register(ServicePincode)
class ServicePincodeAdmin(admin.ModelAdmin):
    list_display = ("pincode", "area_name", "service_area", "is_active")
    list_filter = ("service_area", "is_active")
    search_fields = ("pincode", "area_name", "service_area__name")
    autocomplete_fields = ("service_area",)


@admin.register(ScrapMaterial)
class ScrapMaterialAdmin(admin.ModelAdmin):
    list_display = ("id", "name", "price_per_kg", "is_active")
    search_fields = ("name",)
    list_filter = ("is_active",)


@admin.register(TimeSlot)
class TimeSlotAdmin(admin.ModelAdmin):
    search_fields = ("start_time", "end_time")


@admin.register(WasteType)
class WasteTypeAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "name",
        "is_active",
        "created_at",
        "updated_at",
    )
    list_filter = ("is_active",)
    search_fields = ("name",)
    ordering = ("name",)


@admin.register(WasteCategory)
class WasteCategoryAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "name",
        "waste_type",
        "price_per_kg",
        "is_active",
        "created_at",
        "updated_at",
    )
    list_filter = (
        "waste_type",
        "is_active",
    )
    search_fields = (
        "name",
        "waste_type__name",
    )
    autocomplete_fields = ("waste_type",)
    ordering = (
        "waste_type",
        "name",
    )


@admin.register(WasteSubCategory)
class WasteSubCategoryAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "name",
        "category",
        "is_active",
        "created_at",
        "updated_at",
    )
    list_filter = (
        "category__waste_type",
        "category",
        "is_active",
    )
    search_fields = (
        "name",
        "category__name",
        "category__waste_type__name",
    )
    autocomplete_fields = ("category",)
    ordering = (
        "category",
        "name",
    )
