"""Integracion con Mercado Pago (Checkout Pro)."""
import mercadopago

from .models import Payment, SiteConfig


def create_preference(request, payment: Payment) -> str | None:
    """Crea una preferencia de pago y devuelve la URL de checkout (init_point)."""
    config = SiteConfig.get()
    sdk = mercadopago.SDK(config.mp_access_token)

    success_url = request.build_absolute_uri('/pago/retorno/')
    data = {
        'items': [{
            'title': f'Suscripcion FitTrack - {payment.months} mes(es)',
            'quantity': 1,
            'unit_price': float(payment.amount),
            'currency_id': payment.currency,
        }],
        'payer': {'email': payment.user.email or f'{payment.user.username}@fittrack.local'},
        'external_reference': str(payment.pk),
        'back_urls': {
            'success': success_url,
            'failure': success_url,
            'pending': success_url,
        },
        'notification_url': request.build_absolute_uri('/webhook/mercadopago/'),
        'statement_descriptor': 'FITTRACK',
    }
    # auto_return solo funciona con URLs publicas (no localhost)
    if 'localhost' not in success_url and '127.0.0.1' not in success_url:
        data['auto_return'] = 'approved'

    result = sdk.preference().create(data)
    if result.get('status') not in (200, 201):
        return None
    response = result['response']
    payment.mp_preference_id = response.get('id', '')
    payment.save()
    return response.get('init_point')


def verify_and_apply(mp_payment_id: str) -> Payment | None:
    """Consulta un pago en MP y, si esta aprobado, activa los meses (idempotente)."""
    config = SiteConfig.get()
    if not config.mp_access_token:
        return None
    sdk = mercadopago.SDK(config.mp_access_token)
    result = sdk.payment().get(mp_payment_id)
    if result.get('status') != 200:
        return None
    info = result['response']
    external_ref = info.get('external_reference')
    if not external_ref:
        return None
    try:
        payment = Payment.objects.get(pk=int(external_ref))
    except (Payment.DoesNotExist, ValueError):
        return None

    mp_status = info.get('status')
    payment.mp_payment_id = str(info.get('id', ''))
    if mp_status == 'approved' and payment.status != 'approved':
        payment.status = 'approved'
        payment.save()
        sub = payment.user.subscription
        sub.add_months(payment.months)
    elif mp_status in ('rejected', 'cancelled') and payment.status == 'pending':
        payment.status = 'rejected'
        payment.save()
    else:
        payment.save()
    return payment
