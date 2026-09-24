from django.contrib import admin

from .models import CustomerProfile, Address


@admin.register(CustomerProfile)
class CustomerProfileAdmin(admin.ModelAdmin):
    list_display = ("id", "user")
    search_fields = ("user__phone_number", "email")
    ordering = ("id",)


@admin.register(Address)
class AddressAdmin(admin.ModelAdmin):
    autocomplete_fields = ("pincode",)
    list_select_related = ("customer__user", "pincode")
    list_display = (
        "id",
        "customer",
        "address_type",
        "house_no",
        "area",
        "city",
        "pincode",
    )
    search_fields = (
        "customer__user__phone_number",
        "customer__email",
        "house_no",
        "area",
        "city",
        "pincode__pincode",
    )
    list_filter = ("address_type",)
    ordering = ("id",)
