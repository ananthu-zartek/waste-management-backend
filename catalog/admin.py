from django.contrib import admin

from .models import QuickAction, WasteType, WasteCategory, WasteSubCategory, TimeSlot
from .models import ScrapMaterial
from .models import ServiceArea, ServiceDay, ServicePincode


@admin.register(ServiceDay)
class ServiceDayAdmin(admin.ModelAdmin):
    list_display = ("code", "day_name")
    ordering = ("id",)

    @admin.display(description="Day")
    def day_name(self, obj):
        return obj.get_code_display()


@admin.register(QuickAction)
class QuickActionAdmin(admin.ModelAdmin):
    list_display = ("id", "title", "subtitle", "sort_order")
    search_fields = ("title", "subtitle")
    ordering = ("sort_order", "id")


class ServicePincodeInline(admin.TabularInline):
    model = ServicePincode
    extra = 1
    can_delete = True
    readonly_fields = ("pincode_id",)
    fields = ("pincode_id", "pincode", "area_name", "is_active")

    @admin.display(description="ID")
    def pincode_id(self, obj):
        return obj.pk if obj.pk else ""


@admin.register(ServiceArea)
class ServiceAreaAdmin(admin.ModelAdmin):
    list_display = ("id", "name", "is_active")
    list_filter = ("is_active",)
    search_fields = ("name",)
    inlines = (ServicePincodeInline,)


@admin.register(ServicePincode)
class ServicePincodeAdmin(admin.ModelAdmin):
    search_fields = ("pincode", "area_name", "service_area__name")
    def get_model_perms(self, request):
        return {}


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


class WasteSubCategoryInline(admin.TabularInline):
    model = WasteSubCategory
    extra = 1
    readonly_fields = ("subcategory_id",)
    fields = ("subcategory_id", "name", "is_active")

    @admin.display(description="ID")
    def subcategory_id(self, obj):
        return obj.pk if obj.pk else ""


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
    inlines = (WasteSubCategoryInline,)
    ordering = (
        "waste_type",
        "name",
    )


@admin.register(WasteSubCategory)
class WasteSubCategoryAdmin(admin.ModelAdmin):
    search_fields = ("name", "category__name", "category__waste_type__name")
    def get_model_perms(self, request):
        return {}
