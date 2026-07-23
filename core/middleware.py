from datetime import date, timedelta

from django.shortcuts import redirect
from django.urls import reverse

from .models import SiteConfig, Subscription

# Rutas accesibles aunque la suscripcion este vencida
EXEMPT_PREFIXES = (
    '/login', '/logout', '/registro', '/suscripcion', '/pago',
    '/webhook', '/admin', '/static', '/media',
)


class SubscriptionMiddleware:
    """Bloquea la plataforma a usuarios sin suscripcion activa (los admin no pagan)."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        user = request.user
        if user.is_authenticated and not user.is_staff:
            path = request.path
            if not any(path.startswith(p) for p in EXEMPT_PREFIXES):
                sub = getattr(user, 'subscription', None)
                if sub is None:
                    config = SiteConfig.get()
                    sub = Subscription.objects.create(
                        user=user,
                        trial_ends=date.today() + timedelta(days=config.trial_days),
                    )
                if not sub.is_active:
                    return redirect(reverse('subscription'))
        return self.get_response(request)
