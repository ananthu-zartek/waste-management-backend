from django.contrib.auth.models import AbstractBaseUser, PermissionsMixin
from django.core.validators import MinValueValidator
from django.db import models
from .managers import UserManager
from phonenumber_field.modelfields import PhoneNumberField


class User(AbstractBaseUser, PermissionsMixin):
    class UserType(models.TextChoices):
        ADMIN = "admin", "Admin"
        CUSTOMER = "customer", "Customer"
        DRIVER = "driver", "Driver"

    phone_number = PhoneNumberField(unique=True)
    user_type = models.CharField(
        max_length=20,
        choices=UserType.choices,
        default=UserType.CUSTOMER,
    )
    is_active = models.BooleanField(default=True)
    is_staff = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    objects = UserManager()
    USERNAME_FIELD = "phone_number"
    REQUIRED_FIELDS = []

    def __str__(self):
        return f"{self.phone_number} - {self.user_type}"


class TimeStampedModel(models.Model):
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        abstract = True


class SystemConfiguration(TimeStampedModel):
    minimum_booking_weight = models.DecimalField(
        max_digits=8, decimal_places=2, default=5, validators=[MinValueValidator(0)]
    )
    advance_booking_duration_hours = models.PositiveSmallIntegerField(default=24)
    cancellation_cutoff_hours = models.PositiveSmallIntegerField(default=4)
    max_bookings_per_driver_slot = models.PositiveSmallIntegerField(
        default=4,
        validators=[MinValueValidator(1)],
        verbose_name="Max bookings per slot",
    )
    default_service_days = models.ManyToManyField(
        "catalog.ServiceDay", blank=True, related_name="system_configurations"
    )
    maintenance_mode = models.BooleanField(default=False)

    class Meta:
        verbose_name = "System configuration"
        verbose_name_plural = "System configuration"

    def __str__(self):
        return "System configuration"
