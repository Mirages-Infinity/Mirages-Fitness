from datetime import date, timedelta

from django.contrib.auth.models import User
from django.db.models.signals import post_save
from django.dispatch import receiver

from .models import SiteConfig, Subscription


@receiver(post_save, sender=User)
def create_subscription(sender, instance, created, **kwargs):
    """Al crear un usuario, arranca su periodo de prueba gratis."""
    if created:
        config = SiteConfig.get()
        Subscription.objects.get_or_create(
            user=instance,
            defaults={'trial_ends': date.today() + timedelta(days=config.trial_days)},
        )
