"""Filtros de plantilla para FitTrack: conversion de unidad de peso."""
from django import template

register = template.Library()

KG_TO_LB = 2.20462


def _to_float(value):
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0


@register.filter
def to_unit(value, unit):
    """Convierte un peso guardado en kg a la unidad preferida del usuario."""
    kg = _to_float(value)
    return round(kg * KG_TO_LB, 1) if unit == 'lb' else round(kg, 1)


@register.filter
def unit_label(unit):
    return 'lb' if unit == 'lb' else 'kg'
