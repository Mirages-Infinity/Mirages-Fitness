def preferences(request):
    """Pone la unidad de peso preferida del usuario a disposicion de cualquier
    template, sin tener que agregarla a mano en cada vista."""
    unit = 'kg'
    if request.user.is_authenticated:
        profile = getattr(request.user, 'profile', None)
        if profile:
            unit = profile.unit
    return {'weight_unit': unit}
