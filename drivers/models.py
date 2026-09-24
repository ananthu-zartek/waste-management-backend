from django.db import models

from users.models import TimeStampedModel, User


class DriverProfile(TimeStampedModel):
    user = models.OneToOneField(
        User,
        on_delete=models.CASCADE,
        related_name="driver_profile",
        limit_choices_to={"user_type": User.UserType.DRIVER},
    )
    name = models.CharField(max_length=100, null=True, blank=True)
    email = models.EmailField(null=True, blank=True)
    license_number = models.CharField(max_length=100, unique=True)
    vehicle_number = models.CharField(max_length=50, unique=True)
    is_available = models.BooleanField(default=True)
    service_pincodes = models.ManyToManyField(
        "catalog.ServicePincode",
        related_name="drivers",
        blank=True,
        limit_choices_to={"is_active": True, "service_area__is_active": True},
    )

    def __str__(self):
        return f"{self.user} - {self.vehicle_number}"


class DriverSlot(models.Model):
    driver = models.ForeignKey(
        DriverProfile,
        on_delete=models.CASCADE,
        related_name="driver_slots",
    )
    slot = models.ForeignKey(
        "catalog.TimeSlot",
        on_delete=models.PROTECT,
        related_name="driver_slots",
        limit_choices_to={"is_active": True},
    )
    date = models.DateField()
    booking = models.OneToOneField(
        "bookings.Booking",
        on_delete=models.CASCADE,
        related_name="driver_slot",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        indexes = [models.Index(fields=["driver", "slot", "date"])]

    def __str__(self):
        return f"{self.driver} - {self.date} - Booking {self.booking_id}"
