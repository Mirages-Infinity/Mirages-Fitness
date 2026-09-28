from datetime import date, timedelta

from django.contrib import messages
from django.contrib.auth import login
from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib.auth.models import User
from django.db.models import Count, Q
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from django.http import HttpResponse
from django.views.decorators.csrf import csrf_exempt

from .forms import (
    CardioItemForm, CategoryForm, ExerciseForm, PlanWizardForm, ProfileForm,
    RegisterForm, RoutineItemForm, SiteConfigForm,
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
    total_sets = sum(i.total_sets for i in items)
    done_sets = sum(min(i.sets_done, i.total_sets) for i in items)
    return render(request, 'user/workout.html', {
        'items': items,
        'day': day,
        'day_name': dict(DAYS)[day],
        'is_today': day == date.today().weekday(),
        'total_sets': total_sets,
        'done_sets': done_sets,
        'progress_pct': int(done_sets / total_sets * 100) if total_sets else 0,
        'done_today': WorkoutLog.objects.filter(user=request.user, date=date.today()).exists(),
        'default_rest': get_profile(request.user).default_rest,
        'active_tab': 'home',
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
    profile = get_profile(request.user)
    form = ProfileForm(request.POST or None, instance=profile)
    if request.method == 'POST' and form.is_valid():
        form.save()
        messages.success(request, 'Preferencias guardadas.')
        return redirect('profile')
    return render(request, 'user/profile.html', {
        'form': form, 'profile': profile,
        'sub': getattr(request.user, 'subscription', None),
        'active_tab': 'profile',
    })


@login_required
def routine_item_edit(request, pk):
    item = get_object_or_404(RoutineItem, pk=pk, user=request.user)
    form = item_form_class(item.exercise)(request.POST or None, instance=item)
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
    exercises = Exercise.objects.select_related('category')
    if selected:
        exercises = exercises.filter(category_id=selected)
    if equipment:
        exercises = exercises.filter(equipment=equipment)
    if query:
        exercises = exercises.filter(
            Q(title__icontains=query) | Q(description__icontains=query)
        )
    context = {
        'categories': categories,
        'exercises': exercises,
        'equipments': Exercise.EQUIPMENT,
        'equipment': equipment,
        'selected': int(selected) if selected and selected.isdigit() else None,
        'query': query,
        'active_tab': 'catalog',
    }
    return render(request, 'user/catalog.html', context)


@login_required
def exercise_add(request, pk):
    exercise = get_object_or_404(Exercise, pk=pk)
    form_class = item_form_class(exercise)
    if request.method == 'POST':
        form = form_class(request.POST)
        days = request.POST.getlist('days')
        if form.is_valid() and days:
            profile = get_profile(request.user)
            for d in days:
                item = RoutineItem(
                    user=request.user, exercise=exercise, day=int(d),
                    rest_seconds=profile.default_rest,
                )
                for field, value in form.cleaned_data.items():
                    setattr(item, field, value)
                item.save()
            names = ', '.join(dict(DAYS)[int(d)] for d in sorted(days))
            messages.success(request, f'{exercise.title} agregado a: {names}.')
            return redirect('routine_day', day=int(days[0]))
        if not days:
            messages.error(request, 'Selecciona al menos un dia.')
    else:
        form = form_class()
    return render(request, 'user/exercise_add.html', {
        'exercise': exercise, 'form': form, 'days': DAYS,
        'today': date.today().weekday(), 'active_tab': 'catalog',
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
    for item in items:
        sets_done = checks.get(item.pk, 0)
        if not sets_done:
            continue
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
    return redirect('home')


@login_required
def history(request):
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
        {'date': d, 'logs': lgs, 'total_kg': sum(l.weight * l.sets * l.reps for l in lgs)}
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
        'active_tab': 'history',
    })


@login_required
def progress(request, pk):
    exercise = get_object_or_404(Exercise, pk=pk)
    logs = list(
        WorkoutLog.objects
        .filter(user=request.user, exercise=exercise)
        .order_by('date', 'id')
    )
    is_cardio = exercise.kind == 'cardio'

    def metric(log):
        if is_cardio:
            return float(log.distance_km or 0) or float(log.duration_min or 0)
        return float(log.weight)

    values = [metric(l) for l in logs]
    first_val = values[0] if values else 0
    last_val = values[-1] if values else 0
    diff = last_val - first_val
    max_val = max(values, default=0)
    chart = [
        {'date': l.date, 'value': v, 'pct': (v / max_val * 100) if max_val else 0}
        for l, v in zip(logs, values)
    ]
    # Unidad: km si hay distancia; min si solo hay duracion
    unit = 'kg'
    if is_cardio:
        unit = 'km' if any(l.distance_km for l in logs) else 'min'
    return render(request, 'user/progress.html', {
        'exercise': exercise, 'logs': logs[::-1], 'chart': chart,
        'first_val': first_val, 'last_val': last_val, 'diff': diff,
        'unit': unit, 'is_cardio': is_cardio,
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
