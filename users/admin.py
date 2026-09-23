from django.contrib import admin
from .models import User


@admin.register(User)
class UserAdmin(admin.ModelAdmin):
    list_display = (
        "phone_number",
        "user_type",
        "is_active",
        "is_staff",
    )
    search_fields = ("phone_number",)
