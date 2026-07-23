"""Validacion de RUT chileno (modulo 11)."""
import re

from django.core.exceptions import ValidationError


def normalize_rut(value: str) -> str:
    """Limpia el RUT y lo deja como '12345678-9'. Lanza ValidationError si es invalido."""
    rut = re.sub(r'[^0-9kK]', '', value or '').upper()
    if len(rut) < 7:
        raise ValidationError('El RUT es demasiado corto.')
    body, dv = rut[:-1], rut[-1]
    if not body.isdigit():
        raise ValidationError('El RUT solo puede contener numeros y digito verificador.')

    total, factor = 0, 2
    for digit in reversed(body):
        total += int(digit) * factor
        factor = 2 if factor == 7 else factor + 1
    remainder = 11 - (total % 11)
    expected = '0' if remainder == 11 else 'K' if remainder == 10 else str(remainder)

    if dv != expected:
        raise ValidationError('El RUT no es valido (digito verificador incorrecto).')
    return f'{body}-{dv}'


def format_rut(rut: str) -> str:
    """'12345678-9' -> '12.345.678-9' para mostrar."""
    if '-' not in rut:
        return rut
    body, dv = rut.split('-')
    parts = []
    while len(body) > 3:
        parts.insert(0, body[-3:])
        body = body[:-3]
    parts.insert(0, body)
    return '.'.join(parts) + '-' + dv
