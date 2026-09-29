from datetime import date, timedelta

from django.contrib import messages
from django.contrib.auth import login
from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib.auth.models import User
from django.db.models import Count, Max, Q
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from django.http import HttpResponse
from django.views.decorators.csrf import csrf_exempt

from .forms import (
    CardioItemForm, CategoryForm, ExerciseForm, PlanWizardForm, ProfileForm,
    QuickLogForm, RegisterForm, RoutineItemForm, SiteConfigForm,
)
from .models import (
    Category, DailyCheck, Exercise, Payment, Profile, RoutineItem, RoutinePlan,
    RoutinePlanItem, SiteConfig, Subscription, WorkoutLog,
)
from .payments import create_preference, verify_and_apply
from .planner import generate_plan


def item_form_class(exercise):
    """Formulario segun el tipo de ejercicio."""
    return CardioItemForm if exercise.kind == 'cardio' else RoutineItemForm


def get_profile(user):
    profile, _ = Profile.objects.get_or_create(user=user)
    return profile


def day_items(user, day, with_progress=True):
    """Ejercicios del dia con su progreso de hoy ya resuelto."""
    items = list(
        RoutineItem.objects
        .filter(user=user, day=day)
        .select_related('exercise', 'exercise__category')
    )
    if with_progress:
        checks = {
            c.routine_item_id: c
            for c in DailyCheck.objects.filter(
                user=user, date=date.today(), routine_item__in=items,
            )
        }
        for item in items:
            check = checks.get(item.pk)
            item.sets_done = check.sets_done if check else 0
            item.is_checked = item.sets_done >= item.total_sets
    return items


def group_by_zone(items):
    """Agrupa los ejercicios del dia por zona del cuerpo, con su progreso."""
    zones = {}
    for item in items:
        cat = item.exercise.category
        zone = zones.setdefault(cat.pk, {
            'category': cat, 'items': [], 'done': 0, 'total': 0,
        })
        zone['items'].append(item)
        zone['total'] += item.total_sets
        zone['done'] += min(getattr(item, 'sets_done', 0), item.total_sets)
    for zone in zones.values():
        zone['pct'] = int(zone['done'] / zone['total'] * 100) if zone['total'] else 0
        zone['complete'] = zone['pct'] == 100
    return sorted(zones.values(), key=lambda z: (z['category'].order, z['category'].name))


DAYS = RoutineItem.DAYS


def suggest_weight(user, item):
    """Sugiere el proximo peso segun el ultimo registro de este ejercicio.

    Heuristica simple: si la ultima vez que se registro este ejercicio el
    peso era igual o mayor al que tiene ahora en la rutina (no lo subiste
    todavia a mano), sugiere subirlo un poco. No pretende ser un algoritmo
    de progresion "inteligente", solo un empujon util basado en el
    historial real del usuario.
    """
    if item.exercise.kind == 'cardio':
        return None
    last = (
        WorkoutLog.objects.filter(user=user, exercise=item.exercise)
        .exclude(date=date.today())
        .order_by('-date', '-id')
        .first()
    )
    if not last or float(last.weight) <= 0:
        return None
    if float(item.weight) > float(last.weight):
        return None  # ya se subio el peso desde el ultimo registro
    increment = 1.0 if item.exercise.equipment in ('dumbbell', 'bodyweight', 'band') else 2.5
    suggested = float(last.weight) + increment
    if suggested <= float(item.weight):
        return None
    return {'last': float(last.weight), 'suggested': suggested}


def is_admin(user):
    return user.is_authenticated and user.is_staff


admin_required = user_passes_test(is_admin, login_url='login')


# ---------------------------------------------------------------- Auth

def register_view(request):
    if request.user.is_authenticated:
        return redirect('home')
    form = RegisterForm(request.POST or None)
    if request.method == 'POST' and form.is_valid():
        user = form.save()
        login(request, user)
        messages.success(request, f'¡Bienvenido, {user.username}! Tu cuenta fue creada.')
        return redirect('home')
    return render(request, 'auth/register.html', {'form': form})


# ---------------------------------------------------------------- Usuario

@login_required
def home(request):
    today_idx = date.today().weekday()
    items = day_items(request.user, today_idx)
    zones = group_by_zone(items)

    total_sets = sum(i.total_sets for i in items)
    done_sets = sum(min(i.sets_done, i.total_sets) for i in items)
    progress_pct = int(done_sets / total_sets * 100) if total_sets else 0
    checked_count = sum(1 for i in items if i.is_checked)

    done_today = WorkoutLog.objects.filter(user=request.user, date=date.today()).exists()
    logged_days = list(
        WorkoutLog.objects.filter(user=request.user)
        .values_list('date', flat=True).distinct()
    )

    # Si hoy toca descanso, ofrecemos el proximo dia con entrenamiento
    week = sorted(set(
        RoutineItem.objects.filter(user=request.user).values_list('day', flat=True)
    ))
    next_day = None
    if not items and week:
        upcoming = [d for d in week if d > today_idx] or week
        next_day = {'day': upcoming[0], 'name': dict(DAYS)[upcoming[0]]}

    context = {
        'items': items,
        'zones': zones,
        'has_routine': bool(week),
        'next_day': next_day,
        'today_name': dict(DAYS)[today_idx],
        'done_today': done_today,
        'total_logs': len(set(logged_days)),
        'streak': current_streak(set(logged_days)),
        'checked_count': checked_count,
        'total_sets': total_sets,
        'done_sets': done_sets,
        'progress_pct': progress_pct,
        # circunferencia del anillo de progreso (r=52)
        'ring_offset': 327 - (327 * progress_pct / 100),
        'sub': getattr(request.user, 'subscription', None),
        'active_tab': 'home',
    }
    return render(request, 'user/home.html', context)


def current_streak(days):
    """Dias consecutivos entrenados hasta hoy (o ayer, si hoy aun no entrena)."""
    if not days:
        return 0
    from datetime import timedelta
    cursor = date.today()
    if cursor not in days:
        cursor -= timedelta(days=1)
        if cursor not in days:
            return 0
    streak = 0
    while cursor in days:
        streak += 1
        cursor -= timedelta(days=1)
    return streak


@login_required
def workout(request, day=None):
    """Modo entrenamiento: ejercicio por ejercicio, con temporizador."""
    if day is None:
        day = date.today().weekday()
    day = int(day)
    items = day_items(request.user, day)
    for item in items:
        item.suggestion = suggest_weight(request.user, item)
        item.alternatives = Exercise.objects.filter(
            category=item.exercise.category,
        ).exclude(pk=item.exercise.pk).select_related('category')[:12]
    total_sets = sum(i.total_sets for i in items)
    done_sets = sum(min(i.sets_done, i.total_sets) for i in items)
    profile = get_profile(request.user)
    return render(request, 'user/workout.html', {
        'items': items,
        'day': day,
        'day_name': dict(DAYS)[day],
        'is_today': day == date.today().weekday(),
        'total_sets': total_sets,
        'done_sets': done_sets,
        'progress_pct': int(done_sets / total_sets * 100) if total_sets else 0,
        'done_today': WorkoutLog.objects.filter(user=request.user, date=date.today()).exists(),
        'default_rest': profile.default_rest,
        'active_tab': 'home',
        'hide_nav': True,
    })


@login_required
@require_POST
def set_done(request, pk):
    """Suma (o resta) una serie completada hoy. Responde JSON para el modo entrenamiento."""
    item = get_object_or_404(RoutineItem, pk=pk, user=request.user)
    check, _ = DailyCheck.objects.get_or_create(
        routine_item=item, date=date.today(), defaults={'user': request.user},
    )
    action = request.POST.get('action', 'add')
    if action == 'add':
        check.sets_done = min(check.sets_done + 1, item.total_sets)
    elif action == 'remove':
        check.sets_done = max(check.sets_done - 1, 0)
    elif action == 'complete':
        check.sets_done = item.total_sets
    else:  # toggle: completa o reinicia el ejercicio
        check.sets_done = 0 if check.sets_done >= item.total_sets else item.total_sets
    check.save()

    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        from django.http import JsonResponse
        items = day_items(request.user, item.day)
        total = sum(i.total_sets for i in items)
        done = sum(min(i.sets_done, i.total_sets) for i in items)
        return JsonResponse({
            'sets_done': check.sets_done,
            'total_sets': item.total_sets,
            'complete': check.sets_done >= item.total_sets,
            'rest_seconds': item.rest_seconds,
            'day_pct': int(done / total * 100) if total else 0,
            'day_done': done,
            'day_total': total,
        })
    return redirect(request.POST.get('next') or 'home')


@login_required
def routine_view(request, day=None):
    if day is None:
        day = date.today().weekday()
    day = int(day)
    if not 0 <= day <= 6:
        day = 0
    items = day_items(request.user, day, with_progress=False)
    # Cuantos ejercicios tiene cada dia, para las pastillas de arriba
    counts = dict(
        RoutineItem.objects.filter(user=request.user)
        .values_list('day').annotate(n=Count('id'))
    )
    context = {
        'items': items,
        'zones': group_by_zone(items),
        'day': day,
        'day_name': dict(DAYS)[day],
        'days': [(value, name, counts.get(value, 0)) for value, name in DAYS],
        'total_items': sum(counts.values()),
        'active_tab': 'routine',
    }
    return render(request, 'user/routine.html', context)


# ---------------------------------------------------------------- Historial de planes

@login_required
@require_POST
def plan_save(request):
    """Congela una copia de la rutina activa en el historial (cierre de semana/mes).

    La rutina activa no se toca: el usuario sigue ajustando peso, series o
    ejercicios para el siguiente periodo sobre los mismos RoutineItem.
    """
    items = list(RoutineItem.objects.filter(user=request.user).select_related('exercise'))
    if not items:
        messages.error(request, 'No tienes ejercicios en tu rutina para guardar.')
        return redirect('routine')

    period = request.POST.get('period', 'weekly')
    if period not in ('weekly', 'monthly'):
        period = 'weekly'

    today = date.today()
    last_plan = RoutinePlan.objects.filter(user=request.user).order_by('-ended_at').first()
    if last_plan:
        started_at = min(last_plan.ended_at + timedelta(days=1), today)
    else:
        started_at = min((i.created_at.date() for i in items), default=today)

    label = request.POST.get('label', '').strip()[:60]
    if not label:
        label = (
            f'Semana del {started_at:%d/%m}' if period == 'weekly'
            else f'{today:%B %Y}'.capitalize()
        )

    plan = RoutinePlan.objects.create(
        user=request.user, period=period, label=label,
        started_at=started_at, ended_at=today,
    )
    RoutinePlanItem.objects.bulk_create([
        RoutinePlanItem(
            plan=plan, exercise=i.exercise, day=i.day, weight=i.weight,
            sets=i.sets, reps=i.reps, duration_min=i.duration_min,
            distance_km=i.distance_km, rest_seconds=i.rest_seconds,
            note=i.note, order=i.order,
        ) for i in items
    ])
    messages.success(
        request,
        f'"{label}" guardado en tu historial con {len(items)} ejercicio{"s" if len(items) != 1 else ""}. '
        'Ahora puedes subir peso, cambiar series o agregar/quitar ejercicios para el siguiente periodo.',
    )
    return redirect('plan_detail', pk=plan.pk)


@login_required
def plan_history(request):
    plans = RoutinePlan.objects.filter(user=request.user).annotate(num_items=Count('items'))
    return render(request, 'user/plan_history.html', {
        'plans': plans, 'active_tab': 'history',
    })


@login_required
def plan_detail(request, pk):
    plan = get_object_or_404(RoutinePlan, pk=pk, user=request.user)
    plan_items = list(plan.items.select_related('exercise', 'exercise__category'))
    by_day = {value: [] for value, _ in DAYS}
    for item in plan_items:
        by_day[item.day].append(item)
    days = [
        {'value': value, 'name': name, 'items': by_day[value]}
        for value, name in DAYS if by_day[value]
    ]
    return render(request, 'user/plan_detail.html', {
        'plan': plan, 'days': days, 'total_items': len(plan_items), 'active_tab': 'history',
    })


@login_required
@require_POST
def plan_delete(request, pk):
    plan = get_object_or_404(RoutinePlan, pk=pk, user=request.user)
    plan.delete()
    messages.success(request, f'"{plan.label}" eliminado del historial.')
    return redirect('plan_history')


# ---------------------------------------------------------------- Plan automatico

@login_required
def plan_wizard(request):
    """La app arma la rutina semanal segun objetivo, nivel y equipamiento."""
    profile = get_profile(request.user)
    if request.method == 'POST':
        form = PlanWizardForm(request.POST)
        if form.is_valid():
            data = form.cleaned_data
            summary = generate_plan(
                request.user,
                days_per_week=data['days_per_week'],
                goal=data['goal'],
                level=data['level'],
                equipment=data['equipment'] or None,
            )
            profile.goal = data['goal']
            profile.level = data['level']
            profile.days_per_week = data['days_per_week']
            profile.save()
            total = sum(s['count'] for s in summary)
            messages.success(
                request,
                f'¡Rutina creada! {len(summary)} dias y {total} ejercicios. '
                'Puedes ajustar pesos y descansos cuando quieras.',
            )
            return redirect('routine_day', day=summary[0]['day'])
    else:
        form = PlanWizardForm(initial={
            'days_per_week': profile.days_per_week,
            'goal': profile.goal,
            'level': profile.level,
        })
    return render(request, 'user/plan_wizard.html', {
        'form': form,
        'has_routine': RoutineItem.objects.filter(user=request.user).exists(),
        'active_tab': 'routine',
    })


@login_required
@require_POST
def item_rest(request, pk):
    """Cambia el descanso entre series de un ejercicio de la rutina."""
    item = get_object_or_404(RoutineItem, pk=pk, user=request.user)
    try:
        seconds = int(request.POST.get('rest_seconds', 60))
    except ValueError:
        seconds = 60
    item.rest_seconds = max(10, min(seconds, 600))
    item.save(update_fields=['rest_seconds'])
    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        from django.http import JsonResponse
        return JsonResponse({'rest_seconds': item.rest_seconds})
    return redirect(request.POST.get('next') or 'workout')


@login_required
@require_POST
def routine_item_set_weight(request, pk):
    """Aplica un peso nuevo con un toque (ej. aceptar la sugerencia de progresion)."""
    from decimal import Decimal, InvalidOperation
    from .forms import kg_from_lb

    item = get_object_or_404(RoutineItem, pk=pk, user=request.user)
    unit = get_profile(request.user).unit
    try:
        weight = Decimal(request.POST.get('weight', str(item.weight)))
    except InvalidOperation:
        weight = item.weight
    item.weight = kg_from_lb(weight) if unit == 'lb' else weight.quantize(Decimal('0.1'))
    item.save(update_fields=['weight'])
    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        from django.http import JsonResponse
        from .templatetags.fittrack_extras import to_unit
        return JsonResponse({'weight': to_unit(item.weight, unit)})
    return redirect(request.POST.get('next') or 'workout')


@login_required
@require_POST
def routine_item_swap(request, pk):
    """Sustituye el ejercicio de un item de la rutina por otro (mismo dia).

    Util cuando en el gimnasio no hay una maquina/equipo disponible: se
    cambia el ejercicio sin tener que borrar y volver a armar el dia.
    """
    item = get_object_or_404(RoutineItem, pk=pk, user=request.user)
    new_exercise = get_object_or_404(Exercise, pk=request.POST.get('exercise'))
    old_title = item.exercise.title
    item.exercise = new_exercise
    if new_exercise.kind == 'cardio':
        item.weight = 0
    item.save()
    messages.success(request, f'Cambiaste "{old_title}" por "{new_exercise.title}".')
    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        from django.http import JsonResponse
        return JsonResponse({'ok': True, 'title': new_exercise.title})
    return redirect(request.POST.get('next') or 'workout')


@login_required
@require_POST
def routine_clear(request):
    RoutineItem.objects.filter(user=request.user).delete()
    messages.success(request, 'Tu rutina fue vaciada. Puedes crear una nueva.')
    return redirect('routine')


@login_required
@require_POST
def routine_bulk_delete(request):
    """Elimina uno, varios o todos los ejercicios de la rutina."""
    day = request.POST.get('day') or 0
    items = RoutineItem.objects.filter(user=request.user)

    single = request.POST.get('single')
    scope = request.POST.get('scope', 'selected')

    if single:
        target = items.filter(pk=single)
    elif scope == 'week':
        target = items
    elif scope == 'day':
        target = items.filter(day=day)
    else:
        target = items.filter(pk__in=request.POST.getlist('items'))

    count = target.count()
    if count:
        target.delete()
        if scope == 'week' and not single:
            messages.success(request, f'Rutina vaciada: {count} ejercicios eliminados.')
        else:
            messages.success(
                request,
                f'{count} ejercicio{"s" if count != 1 else ""} '
                f'eliminado{"s" if count != 1 else ""} de tu rutina.',
            )
    else:
        messages.error(request, 'No seleccionaste ningun ejercicio.')

    if scope == 'week' and not single:
        return redirect('routine')
    return redirect('routine_day', day=int(day))


@login_required
def profile_settings(request):
    from .templatetags.fittrack_extras import to_unit

    profile = get_profile(request.user)
    form = ProfileForm(request.POST or None, instance=profile)
    if request.method == 'POST' and form.is_valid():
        form.save()
        messages.success(request, 'Preferencias guardadas.')
        return redirect('profile')

    pct_table = []
    if profile.bench_1rm or profile.squat_1rm or profile.deadlift_1rm:
        for pct in (50, 60, 70, 75, 80, 85, 90, 95):
            pct_table.append({
                'pct': pct,
                'bench': to_unit(profile.bench_1rm * pct / 100, profile.unit) if profile.bench_1rm else None,
                'squat': to_unit(profile.squat_1rm * pct / 100, profile.unit) if profile.squat_1rm else None,
                'deadlift': to_unit(profile.deadlift_1rm * pct / 100, profile.unit) if profile.deadlift_1rm else None,
            })

    return render(request, 'user/profile.html', {
        'form': form, 'profile': profile,
        'sub': getattr(request.user, 'subscription', None),
        'pct_table': pct_table,
        'active_tab': 'profile',
    })


@login_required
def routine_item_edit(request, pk):
    item = get_object_or_404(RoutineItem, pk=pk, user=request.user)
    unit = get_profile(request.user).unit
    form = item_form_class(item.exercise)(request.POST or None, instance=item, unit=unit)
    if request.method == 'POST' and form.is_valid():
        form.save()
        messages.success(request, f'{item.exercise.title} actualizado.')
        return redirect('routine_day', day=item.day)
    return render(request, 'user/routine_item_form.html', {
        'form': form, 'item': item, 'active_tab': 'routine',
    })


@login_required
def catalog(request):
    categories = Category.objects.annotate(num=Count('exercises'))
    selected = request.GET.get('cat')
    equipment = request.GET.get('eq', '')
    query = request.GET.get('q', '').strip()
    fav_only = request.GET.get('fav') == '1'
    profile = get_profile(request.user)
    favorite_ids = set(profile.favorites.values_list('pk', flat=True))

    exercises = Exercise.objects.select_related('category')
    if selected:
        exercises = exercises.filter(category_id=selected)
    if equipment:
        exercises = exercises.filter(equipment=equipment)
    if query:
        exercises = exercises.filter(
            Q(title__icontains=query) | Q(description__icontains=query)
        )
    if fav_only:
        exercises = exercises.filter(pk__in=favorite_ids)
    context = {
        'categories': categories,
        'exercises': exercises,
        'equipments': Exercise.EQUIPMENT,
        'equipment': equipment,
        'selected': int(selected) if selected and selected.isdigit() else None,
        'query': query,
        'fav_only': fav_only,
        'favorite_ids': favorite_ids,
        'in_routine_ids': set(
            RoutineItem.objects.filter(user=request.user).values_list('exercise_id', flat=True)
        ),
        'DAYS_CHOICES': DAYS,
        'today': date.today().weekday(),
        'active_tab': 'catalog',
    }
    return render(request, 'user/catalog.html', context)


@login_required
@require_POST
def exercise_favorite_toggle(request, pk):
    exercise = get_object_or_404(Exercise, pk=pk)
    profile = get_profile(request.user)
    if profile.favorites.filter(pk=exercise.pk).exists():
        profile.favorites.remove(exercise)
        is_fav = False
    else:
        profile.favorites.add(exercise)
        is_fav = True
    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        from django.http import JsonResponse
        return JsonResponse({'is_favorite': is_fav})
    return redirect(request.POST.get('next') or 'catalog')


@login_required
@require_POST
def catalog_bulk_add(request):
    """Agrega varios ejercicios del catalogo a la vez a los dias elegidos.

    Si un ejercicio ya esta en un dia, ese dia se omite (no se pisa): para
    cambiarle el peso o las series hay que editarlo desde 'Mi rutina'.
    """
    exercise_ids = request.POST.getlist('exercises')
    days = request.POST.getlist('days')
    if not exercise_ids or not days:
        messages.error(request, 'Selecciona al menos un ejercicio y un dia.')
        return redirect('catalog')

    exercises = list(Exercise.objects.filter(pk__in=exercise_ids))
    profile = get_profile(request.user)
    added = skipped = 0
    for exercise in exercises:
        for d in days:
            d = int(d)
            _, created = RoutineItem.objects.get_or_create(
                user=request.user, exercise=exercise, day=d,
                defaults={'rest_seconds': profile.default_rest},
            )
            if created:
                added += 1
            else:
                skipped += 1

    msg = f'{len(exercises)} ejercicio{"s" if len(exercises) != 1 else ""}: {added} agregado{"s" if added != 1 else ""}'
    if skipped:
        msg += f', {skipped} ya estaba{"n" if skipped != 1 else ""} en tu rutina (sin cambios)'
    messages.success(request, msg + '.')
    return redirect('routine_day', day=int(days[0]))


@login_required
def exercise_add(request, pk):
    exercise = get_object_or_404(Exercise, pk=pk)
    form_class = item_form_class(exercise)
    profile = get_profile(request.user)
    if request.method == 'POST':
        form = form_class(request.POST, unit=profile.unit)
        days = request.POST.getlist('days')
        if form.is_valid() and days:
            added, updated = [], []
            for d in days:
                d = int(d)
                # Si el ejercicio ya esta en ese dia, lo actualiza en vez de
                # duplicarlo (p. ej. si el usuario vuelve al catalogo a
                # cambiarle el peso o las series).
                item, created = RoutineItem.objects.get_or_create(
                    user=request.user, exercise=exercise, day=d,
                    defaults={'rest_seconds': profile.default_rest},
                )
                for field, value in form.cleaned_data.items():
                    setattr(item, field, value)
                item.save()
                (added if created else updated).append(d)

            parts = []
            if added:
                parts.append('agregado a ' + ', '.join(dict(DAYS)[d] for d in sorted(added)))
            if updated:
                parts.append('actualizado en ' + ', '.join(dict(DAYS)[d] for d in sorted(updated)) + ' (ya estaba en tu rutina)')
            messages.success(request, f'{exercise.title}: ' + '; '.join(parts) + '.')
            return redirect('routine_day', day=int(days[0]))
        if not days:
            messages.error(request, 'Selecciona al menos un dia.')
    existing = list(RoutineItem.objects.filter(user=request.user, exercise=exercise))
    existing_days = {i.day for i in existing}

    if request.method != 'POST':
        # Si ya esta en la rutina, precarga los valores actuales en vez de
        # mostrar el formulario en blanco: el usuario esta editando, no
        # agregando de cero.
        initial = None
        if existing:
            fields = form_class.base_fields.keys()
            initial = {f: getattr(existing[0], f) for f in fields if f != 'rest_seconds'}
        form = form_class(initial=initial, unit=profile.unit)

    return render(request, 'user/exercise_add.html', {
        'exercise': exercise, 'form': form, 'days': DAYS,
        'today': date.today().weekday(), 'existing_days': existing_days,
        'is_favorite': profile.favorites.filter(pk=exercise.pk).exists(),
        'unit': profile.unit,
        'active_tab': 'catalog',
    })


@login_required
@require_POST
def log_today(request):
    today_idx = date.today().weekday()
    items = RoutineItem.objects.filter(user=request.user, day=today_idx)
    if not items.exists():
        messages.error(request, 'No tienes ejercicios en la rutina de hoy.')
        return redirect('home')
    if WorkoutLog.objects.filter(user=request.user, date=date.today()).exists():
        messages.error(request, 'Ya registraste tu entrenamiento de hoy.')
        return redirect('home')
    checks = {
        c.routine_item_id: c.sets_done
        for c in DailyCheck.objects.filter(
            user=request.user, date=date.today(), routine_item__in=items, sets_done__gt=0,
        )
    }
    if not checks:
        messages.error(request, 'Marca al menos una serie completada antes de registrar.')
        return redirect('home')

    prs = []
    for item in items:
        sets_done = checks.get(item.pk, 0)
        if not sets_done:
            continue
        if item.exercise.kind != 'cardio' and item.weight > 0:
            prev_max = WorkoutLog.objects.filter(
                user=request.user, exercise=item.exercise,
            ).exclude(date=date.today()).aggregate(m=Max('weight'))['m']
            if prev_max is not None and item.weight > prev_max:
                prs.append(item.exercise.title)
        WorkoutLog.objects.create(
            user=request.user,
            exercise=item.exercise,
            weight=item.weight,
            sets=sets_done if item.exercise.kind != 'cardio' else item.sets,
            reps=item.reps,
            duration_min=item.duration_min,
            distance_km=item.distance_km,
        )
    messages.success(request, f'¡Entrenamiento registrado ({len(checks)} ejercicios)! 🔥')
    if prs:
        messages.success(request, f'🏆 ¡Nuevo récord personal en {", ".join(prs)}!')
    return redirect('home')


@login_required
def quick_log(request):
    """Registro suelto: anota un ejercicio hecho fuera de la rutina de hoy
    (otro gimnasio, algo improvisado) sin pasar por el modo entrenamiento."""
    profile = get_profile(request.user)
    if request.method == 'POST':
        form = QuickLogForm(request.POST, unit=profile.unit)
        if form.is_valid():
            data = form.cleaned_data
            exercise = data['exercise']
            WorkoutLog.objects.create(
                user=request.user, exercise=exercise,
                weight=data['weight'] or 0,
                sets=data['sets'] or 1,
                reps=data['reps'] or 1,
                duration_min=data['duration_min'],
                distance_km=data['distance_km'],
            )
            messages.success(request, f'{exercise.title} registrado en tu historial.')
            return redirect('history')
    else:
        form = QuickLogForm(unit=profile.unit)
    return render(request, 'user/quick_log.html', {
        'form': form, 'unit': profile.unit, 'active_tab': 'history',
    })


@login_required
def history(request):
    from .templatetags.fittrack_extras import to_unit

    weight_unit = get_profile(request.user).unit
    logs = (
        WorkoutLog.objects
        .filter(user=request.user)
        .select_related('exercise', 'exercise__category')
    )
    # Agrupar por fecha
    grouped = {}
    for log in logs:
        grouped.setdefault(log.date, []).append(log)
    sessions = [
        {
            'date': d, 'logs': lgs,
            'total_kg': to_unit(sum(l.weight * l.sets * l.reps for l in lgs), weight_unit),
        }
        for d, lgs in grouped.items()
    ]
    # Ejercicios con historial para ver progreso
    exercises = (
        Exercise.objects
        .filter(workoutlog__user=request.user)
        .annotate(times=Count('workoutlog'))
        .distinct()
    )
    recent_plans = RoutinePlan.objects.filter(user=request.user)[:3]
    return render(request, 'user/history.html', {
        'sessions': sessions, 'exercises': exercises, 'recent_plans': recent_plans,
        'weight_unit': weight_unit,
        'active_tab': 'history',
    })


@login_required
def progress(request, pk):
    from .templatetags.fittrack_extras import to_unit

    exercise = get_object_or_404(Exercise, pk=pk)
    weight_unit = get_profile(request.user).unit
    logs = list(
        WorkoutLog.objects
        .filter(user=request.user, exercise=exercise)
        .order_by('date', 'id')
    )
    is_cardio = exercise.kind == 'cardio'

    def metric(log):
        if is_cardio:
            return float(log.distance_km or 0) or float(log.duration_min or 0)
        return to_unit(log.weight, weight_unit)

    values = [metric(l) for l in logs]
    first_val = values[0] if values else 0
    last_val = values[-1] if values else 0
    diff = last_val - first_val
    max_val = max(values, default=0)
    chart = [
        {'date': l.date, 'value': v, 'pct': (v / max_val * 100) if max_val else 0}
        for l, v in zip(logs, values)
    ]
    # Unidad: km si hay distancia; min si solo hay duracion; kg/lb segun perfil
    unit = weight_unit
    if is_cardio:
        unit = 'km' if any(l.distance_km for l in logs) else 'min'

    # 1RM estimado (formula de Epley): peso * (1 + reps/30). Solo referencial.
    one_rm = None
    best_one_rm = None
    if not is_cardio and logs:
        def epley(log):
            return float(log.weight) * (1 + float(log.reps) / 30)
        one_rm = round(to_unit(epley(logs[-1]), weight_unit), 1)
        best_one_rm = round(to_unit(max(epley(l) for l in logs), weight_unit), 1)

    return render(request, 'user/progress.html', {
        'exercise': exercise, 'logs': logs[::-1], 'chart': chart,
        'first_val': first_val, 'last_val': last_val, 'diff': diff,
        'unit': unit, 'is_cardio': is_cardio,
        'one_rm': one_rm, 'best_one_rm': best_one_rm, 'weight_unit': weight_unit,
        'active_tab': 'history',
    })


# ---------------------------------------------------------------- Suscripcion

@login_required
def subscription(request):
    config = SiteConfig.get()
    sub = getattr(request.user, 'subscription', None)
    payments = Payment.objects.filter(user=request.user, status='approved')[:12]
    return render(request, 'user/subscription.html', {
        'config': config, 'sub': sub, 'payments': payments,
        'active_tab': 'home',
    })


@login_required
@require_POST
def pay_create(request):
    config = SiteConfig.get()
    if not config.payments_ready:
        messages.error(request, 'Los pagos aun no estan configurados. Contacta al administrador.')
        return redirect('subscription')
    payment = Payment.objects.create(
        user=request.user,
        amount=config.monthly_price,
        currency=config.currency,
        months=1,
    )
    checkout_url = create_preference(request, payment)
    if not checkout_url:
        payment.delete()
        messages.error(request, 'No se pudo iniciar el pago. Verifica la configuracion de Mercado Pago.')
        return redirect('subscription')
    return redirect(checkout_url)


@login_required
def pay_return(request):
    """Vuelta desde el checkout de Mercado Pago."""
    mp_payment_id = request.GET.get('payment_id') or request.GET.get('collection_id')
    if mp_payment_id and mp_payment_id != 'null':
        payment = verify_and_apply(mp_payment_id)
        if payment and payment.status == 'approved':
            messages.success(request, '¡Pago aprobado! Tu suscripcion esta activa. 💪')
            return redirect('home')
        if payment and payment.status == 'rejected':
            messages.error(request, 'El pago fue rechazado. Intenta con otro medio de pago.')
            return redirect('subscription')
    status = request.GET.get('status', '')
    if status == 'pending':
        messages.success(request, 'Tu pago esta pendiente de acreditacion. Se activara automaticamente.')
    return redirect('subscription')


@csrf_exempt
def github_webhook(request):
    """Auto-deploy: GitHub avisa aqui cuando hay un push y la app se actualiza sola.

    Requiere las variables de entorno GITHUB_WEBHOOK_SECRET (el mismo secreto
    configurado en GitHub) y PA_WSGI_FILE (ruta del WSGI en PythonAnywhere,
    que al 'tocarse' recarga la web).
    """
    import hashlib
    import hmac
    import os as _os
    import subprocess
    import sys as _sys
    from pathlib import Path as _Path

    from django.conf import settings as dj_settings

    secret = _os.environ.get('GITHUB_WEBHOOK_SECRET', '')
    if not secret or request.method != 'POST':
        return HttpResponse(status=403)
    signature = request.headers.get('X-Hub-Signature-256', '')
    expected = 'sha256=' + hmac.new(secret.encode(), request.body, hashlib.sha256).hexdigest()
    if not hmac.compare_digest(signature, expected):
        return HttpResponse(status=403)

    base = dj_settings.BASE_DIR
    steps = [
        ['git', 'pull'],
        [_sys.executable, 'manage.py', 'migrate', '--noinput'],
        [_sys.executable, 'manage.py', 'collectstatic', '--noinput'],
    ]
    output = []
    for cmd in steps:
        result = subprocess.run(cmd, cwd=base, capture_output=True, text=True, timeout=120)
        output.append(f'$ {" ".join(cmd)}\n{result.stdout}{result.stderr}')

    wsgi_file = _os.environ.get('PA_WSGI_FILE')
    if wsgi_file and _Path(wsgi_file).exists():
        _Path(wsgi_file).touch()  # PythonAnywhere recarga la web al tocar el WSGI
        output.append(f'reload: {wsgi_file}')

    return HttpResponse('\n\n'.join(output), content_type='text/plain')


@csrf_exempt
def mp_webhook(request):
    """Notificaciones de Mercado Pago (IPN / Webhooks)."""
    topic = request.GET.get('topic') or request.GET.get('type')
    mp_payment_id = request.GET.get('id') or request.GET.get('data.id')
    if request.method == 'POST' and not mp_payment_id:
        import json
        try:
            body = json.loads(request.body)
            mp_payment_id = body.get('data', {}).get('id')
            topic = topic or body.get('type')
        except (ValueError, AttributeError):
            pass
    if topic in ('payment', 'payment.created', 'payment.updated') and mp_payment_id:
        verify_and_apply(str(mp_payment_id))
    return HttpResponse(status=200)


# ---------------------------------------------------------------- Admin

@admin_required
def panel(request):
    stats = {
        'exercises': Exercise.objects.count(),
        'categories': Category.objects.count(),
        'users': User.objects.filter(is_staff=False).count(),
        'logs': WorkoutLog.objects.count(),
    }
    recent = Exercise.objects.select_related('category').order_by('-created_at')[:5]
    return render(request, 'panel/dashboard.html', {
        'stats': stats, 'recent': recent, 'active_tab': 'panel',
    })


@admin_required
def panel_categories(request):
    categories = Category.objects.annotate(num=Count('exercises'))
    return render(request, 'panel/categories.html', {
        'categories': categories, 'active_tab': 'panel',
    })


@admin_required
def panel_category_form(request, pk=None):
    category = get_object_or_404(Category, pk=pk) if pk else None
    form = CategoryForm(request.POST or None, instance=category)
    if request.method == 'POST' and form.is_valid():
        form.save()
        messages.success(request, 'Categoria guardada.')
        return redirect('panel_categories')
    return render(request, 'panel/category_form.html', {
        'form': form, 'category': category, 'active_tab': 'panel',
    })


@admin_required
@require_POST
def panel_category_delete(request, pk):
    category = get_object_or_404(Category, pk=pk)
    category.delete()
    messages.success(request, f'Categoria "{category.name}" eliminada.')
    return redirect('panel_categories')


@admin_required
def panel_exercises(request):
    selected = request.GET.get('cat')
    exercises = Exercise.objects.select_related('category')
    if selected:
        exercises = exercises.filter(category_id=selected)
    return render(request, 'panel/exercises.html', {
        'exercises': exercises,
        'categories': Category.objects.all(),
        'selected': int(selected) if selected and selected.isdigit() else None,
        'active_tab': 'panel',
    })


@admin_required
def panel_exercise_form(request, pk=None):
    exercise = get_object_or_404(Exercise, pk=pk) if pk else None
    form = ExerciseForm(request.POST or None, request.FILES or None, instance=exercise)
    if request.method == 'POST' and form.is_valid():
        form.save()
        messages.success(request, 'Ejercicio guardado.')
        return redirect('panel_exercises')
    return render(request, 'panel/exercise_form.html', {
        'form': form, 'exercise': exercise, 'active_tab': 'panel',
    })


@admin_required
@require_POST
def panel_exercise_delete(request, pk):
    exercise = get_object_or_404(Exercise, pk=pk)
    exercise.delete()
    messages.success(request, f'Ejercicio "{exercise.title}" eliminado.')
    return redirect('panel_exercises')


@admin_required
def panel_users(request):
    users = (
        User.objects
        .select_related('subscription', 'profile')
        .annotate(
            num_items=Count('routine_items', distinct=True),
            num_logs=Count('workout_logs', distinct=True),
        )
        .order_by('-date_joined')
    )
    return render(request, 'panel/users.html', {'users': users, 'active_tab': 'panel'})


@admin_required
@require_POST
def panel_user_toggle(request, pk):
    user = get_object_or_404(User, pk=pk)
    if user == request.user:
        messages.error(request, 'No puedes desactivar tu propia cuenta.')
    else:
        user.is_active = not user.is_active
        user.save()
        state = 'activado' if user.is_active else 'desactivado'
        messages.success(request, f'Usuario "{user.username}" {state}.')
    return redirect('panel_users')


@admin_required
def panel_config(request):
    config = SiteConfig.get()
    form = SiteConfigForm(request.POST or None, instance=config)
    if request.method == 'POST' and form.is_valid():
        form.save()
        messages.success(request, 'Configuracion guardada.')
        return redirect('panel_config')
    return render(request, 'panel/config.html', {
        'form': form, 'config': config, 'active_tab': 'panel',
    })


@admin_required
@require_POST
def panel_user_add_month(request, pk):
    user = get_object_or_404(User, pk=pk)
    sub = Subscription.objects.filter(user=user).first()
    if sub is None:
        sub = Subscription.objects.create(user=user, trial_ends=date.today())
    sub.add_months(1)
    config = SiteConfig.get()
    Payment.objects.create(
        user=user, amount=config.monthly_price, currency=config.currency,
        months=1, status='approved', manual=True,
    )
    messages.success(request, f'+1 mes activado para "{user.username}" (hasta {sub.paid_until:%d/%m/%Y}).')
    return redirect('panel_users')


@admin_required
@require_POST
def panel_user_exempt(request, pk):
    """Libera (o vuelve a cobrar) a un usuario del pago de suscripcion."""
    user = get_object_or_404(User, pk=pk)
    sub = Subscription.objects.filter(user=user).first()
    if sub is None:
        sub = Subscription.objects.create(user=user, trial_ends=date.today())
    sub.exempt = not sub.exempt
    sub.save()
    if sub.exempt:
        messages.success(request, f'"{user.username}" liberado de pago: acceso gratis sin limite. 🎁')
    else:
        messages.success(request, f'"{user.username}" vuelve al plan de pago normal.')
    return redirect('panel_users')


@admin_required
@require_POST
def panel_user_delete(request, pk):
    user = get_object_or_404(User, pk=pk)
    if user == request.user:
        messages.error(request, 'No puedes eliminar tu propia cuenta.')
    else:
        user.delete()
        messages.success(request, f'Usuario "{user.username}" eliminado.')
    return redirect('panel_users')
