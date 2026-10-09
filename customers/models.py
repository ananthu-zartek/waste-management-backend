from django.contrib.gis.db import models
from users.models import User
from bookings.models import Booking


class CustomerProfile(models.Model):
    user = models.OneToOneField(
        User,
        on_delete=models.CASCADE,
        related_name="customer_profile",
    )
    name = models.CharField(max_length=100, null=True, blank=True)
    email = models.EmailField(null=True, blank=True)

    @property
    def default_address(self):
        return self.addresses.filter(is_default=True).first()

    @property
    def completed_bookings_count(self):
        return self.bookings.filter(status=Booking.BookingStatus.COMPLETED).count()

    def __str__(self):
        return str(self.user.phone_number)


class Address(models.Model):
    class AddressType(models.TextChoices):
        HOME = "home", "Home"
        WORK = "work", "Work"
        OTHER = "other", "Other"

    customer = models.ForeignKey(
        CustomerProfile,
        on_delete=models.CASCADE,
        related_name="addresses",
    )
    address_type = models.CharField(
        max_length=10,
        choices=AddressType.choices,
    )
    house_no = models.CharField(max_length=100)
    area = models.CharField(max_length=150)
    city = models.CharField(max_length=100)
    location = models.PointField(geography=True, blank=True, null=True)
    is_default = models.BooleanField(default=False)
    pincode = models.ForeignKey(
        "catalog.ServicePincode",
        on_delete=models.SET_NULL,
        null=True,
        related_name="addresses",
        limit_choices_to={"is_active": True, "service_area__is_active": True},
    )

    class Meta:
        verbose_name = "Customer Address"
        verbose_name_plural = "Customer Addresses"

    def __str__(self):
        return f"{self.customer} - {self.address_type}"
