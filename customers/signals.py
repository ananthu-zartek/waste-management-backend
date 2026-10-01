from django.db.models.signals import post_save
from django.dispatch import receiver

from .models import Address


@receiver(post_save, sender=Address)
def clear_other_default_addresses(sender, instance, **kwargs):
    if instance.is_default:
        sender.objects.filter(
            customer_id=instance.customer_id, is_default=True
        ).exclude(pk=instance.pk).update(is_default=False)
