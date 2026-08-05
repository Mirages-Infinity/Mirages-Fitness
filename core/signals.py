from datetime import date, timedelta

from django.contrib.auth.models import User
from django.db.models.signals import post_save
from django.dispatch import receiver

from .models import Profile, SiteConfig, Subscription


@receiver(post_save, sender=User)
def create_user_extras(sender, instance, created, **kwargs):
    """Al crear un usuario: periodo de prueba gratis + perfil de preferencias."""
    if created:
        config = SiteConfig.get()
        Subscription.objects.get_or_create(
            user=instance,
            defaults={'trial_ends': date.today() + timedelta(days=config.trial_days)},
        )
        Profile.objects.get_or_create(user=instance)
