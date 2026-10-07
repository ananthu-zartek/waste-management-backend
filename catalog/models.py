from django.db import models
from django.core.validators import MinValueValidator, RegexValidator

from users.models import TimeStampedModel


class ServiceDay(models.Model):
    class Day(models.TextChoices):
        MONDAY = "mon", "Monday"
        TUESDAY = "tue", "Tuesday"
        WEDNESDAY = "wed", "Wednesday"
        THURSDAY = "thu", "Thursday"
        FRIDAY = "fri", "Friday"
        SATURDAY = "sat", "Saturday"
        SUNDAY = "sun", "Sunday"

    code = models.CharField(max_length=3, choices=Day.choices, unique=True)

    def __str__(self):
        return self.get_code_display()


class QuickAction(TimeStampedModel):
    title = models.CharField(max_length=100, unique=True)
    subtitle = models.CharField(max_length=150)
    sort_order = models.PositiveSmallIntegerField(default=0)

    class Meta:
        ordering = ["sort_order", "id"]

    def __str__(self):
        return self.title


class ServiceArea(TimeStampedModel):
    name = models.CharField(max_length=150, unique=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return self.name


class ServicePincode(TimeStampedModel):
    service_area = models.ForeignKey(
        ServiceArea, on_delete=models.PROTECT, related_name="pincodes"
    )
    pincode = models.CharField(
        max_length=6,
        unique=True,
        validators=[
            RegexValidator(r"^[1-9][0-9]{5}$", "Enter a valid six-digit pincode.")
        ],
    )
    area_name = models.CharField(max_length=150)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["pincode"]

    def __str__(self):
        return f"{self.pincode} - {self.area_name}"


class ScrapMaterial(TimeStampedModel):
    name = models.CharField(max_length=150, unique=True)
    price_per_kg = models.DecimalField(
        max_digits=10, decimal_places=2, validators=[MinValueValidator(0)]
    )
    is_active = models.BooleanField(default=True)

    class Meta:
        constraints = [
            models.CheckConstraint(
                condition=models.Q(price_per_kg__gte=0),
                name="scrap_material_nonnegative_price",
            )
        ]

    def __str__(self):
        return self.name


class TimeSlot(TimeStampedModel):
    start_time = models.TimeField()
    end_time = models.TimeField()
    capacity = models.PositiveSmallIntegerField(default=4, validators=[MinValueValidator(1)])
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["start_time"]
        constraints = [
            models.UniqueConstraint(
                fields=["start_time", "end_time"],
                name="unique_time_slot",
            ),
        ]

    def __str__(self):
        return (
            f"{self.start_time.strftime('%I:%M %p')} - "
            f"{self.end_time.strftime('%I:%M %p')}"
        )


class WasteType(TimeStampedModel):
    name = models.CharField(
        max_length=100,
        unique=True,
    )
    is_active = models.BooleanField(default=True)

    def __str__(self):
        return self.name


class WasteCategory(TimeStampedModel):
    waste_type = models.ForeignKey(
        WasteType,
        on_delete=models.CASCADE,
        related_name="categories",
    )
    name = models.CharField(max_length=100)
    description = models.TextField(blank=True)
    price_per_kg = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=0,
    )
    is_active = models.BooleanField(default=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["waste_type", "name"],
                name="unique_waste_category",
            ),
        ]

    def __str__(self):
        return f"{self.waste_type.name} - {self.name}"


class WasteSubCategory(TimeStampedModel):
    category = models.ForeignKey(
        WasteCategory,
        on_delete=models.CASCADE,
        related_name="subcategories",
    )
    name = models.CharField(max_length=100)
    is_active = models.BooleanField(default=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["category", "name"],
                name="unique_waste_subcategory",
            ),
        ]

    def __str__(self):
        return self.name
