from django.db.models.signals import post_save
from django.dispatch import receiver

from users.models import User
from customers.models import CustomerProfile


@receiver(post_save, sender=User)
def create_customer_profile(sender, instance, created, **kwargs):
    if created and instance.user_type == User.UserType.CUSTOMER:
        CustomerProfile.objects.create(user=instance)
