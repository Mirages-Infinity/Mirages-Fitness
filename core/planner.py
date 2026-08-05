"""Generador de rutinas semanales.

Arma un plan equilibrado repartiendo zonas del cuerpo entre los dias
disponibles, con el volumen (series, reps y descanso) que corresponde
al objetivo y al nivel del usuario.
"""
import random

from .models import Exercise, RoutineItem

# Series / reps / descanso segun objetivo
GOAL_SCHEME = {
    'fuerza':       {'sets': 5, 'reps': 5,  'rest': 180, 'cardio_min': 15},
    'hipertrofia':  {'sets': 4, 'reps': 10, 'rest': 90,  'cardio_min': 15},
    'perder_grasa': {'sets': 3, 'reps': 12, 'rest': 45,  'cardio_min': 30},
    'resistencia':  {'sets': 3, 'reps': 15, 'rest': 60,  'cardio_min': 20},
}

# Cuantos ejercicios extra (o menos) segun nivel
LEVEL_DELTA = {'beginner': -1, 'intermediate': 0, 'advanced': 1}

# Dias de la semana elegidos segun cuantos entrena (0 = lunes)
WEEK_DAYS = {
    1: [0],
    2: [0, 3],
    3: [0, 2, 4],
    4: [0, 1, 3, 4],
    5: [0, 1, 2, 3, 4],
    6: [0, 1, 2, 3, 4, 5],
}

# Rutinas por cantidad de dias: (nombre, [(zona, cantidad), ...])
SPLITS = {
    1: [
        ('Cuerpo completo', [('Pecho', 1), ('Espalda', 1), ('Piernas', 2), ('Hombros', 1), ('Abdomen', 1)]),
    ],
    2: [
        ('Cuerpo completo A', [('Pecho', 2), ('Espalda', 2), ('Piernas', 2), ('Abdomen', 1)]),
        ('Cuerpo completo B', [('Hombros', 2), ('Piernas', 2), ('Espalda', 1), ('Biceps', 1), ('Triceps', 1)]),
    ],
    3: [
        ('Empuje (pecho, hombro, triceps)', [('Pecho', 3), ('Hombros', 2), ('Triceps', 2)]),
        ('Tiron (espalda y biceps)', [('Espalda', 4), ('Biceps', 2), ('Abdomen', 1)]),
        ('Pierna y gluteo', [('Piernas', 4), ('Gluteos', 2), ('Abdomen', 1)]),
    ],
    4: [
        ('Torso A', [('Pecho', 2), ('Espalda', 2), ('Hombros', 1), ('Triceps', 1), ('Biceps', 1)]),
        ('Pierna A', [('Piernas', 3), ('Gluteos', 2), ('Abdomen', 2)]),
        ('Torso B', [('Espalda', 2), ('Pecho', 2), ('Hombros', 2), ('Biceps', 1), ('Triceps', 1)]),
        ('Pierna B', [('Piernas', 3), ('Gluteos', 2), ('Abdomen', 2)]),
    ],
    5: [
        ('Pecho y triceps', [('Pecho', 4), ('Triceps', 3)]),
        ('Espalda y biceps', [('Espalda', 4), ('Biceps', 3)]),
        ('Pierna', [('Piernas', 4), ('Gluteos', 2)]),
        ('Hombro y abdomen', [('Hombros', 4), ('Abdomen', 3)]),
        ('Gluteo y core', [('Gluteos', 3), ('Piernas', 2), ('Abdomen', 2)]),
    ],
    6: [
        ('Empuje A', [('Pecho', 3), ('Hombros', 2), ('Triceps', 2)]),
        ('Tiron A', [('Espalda', 3), ('Biceps', 2), ('Abdomen', 1)]),
        ('Pierna A', [('Piernas', 3), ('Gluteos', 2), ('Abdomen', 1)]),
        ('Empuje B', [('Hombros', 3), ('Pecho', 2), ('Triceps', 2)]),
        ('Tiron B', [('Espalda', 3), ('Biceps', 2), ('Abdomen', 1)]),
        ('Pierna B', [('Gluteos', 3), ('Piernas', 2), ('Abdomen', 1)]),
    ],
}


def _pick(exercises, count, used):
    """Elige `count` ejercicios priorizando los que aun no se usaron."""
    fresh = [e for e in exercises if e.pk not in used]
    random.shuffle(fresh)
    chosen = fresh[:count]
    if len(chosen) < count:  # si la zona tiene pocos ejercicios, repite
        rest = [e for e in exercises if e not in chosen]
        random.shuffle(rest)
        chosen += rest[:count - len(chosen)]
    used.update(e.pk for e in chosen)
    return chosen


def generate_plan(user, days_per_week=3, goal='hipertrofia', level='beginner',
                  equipment=None, replace=True):
    """Crea la rutina semanal del usuario y devuelve el resumen por dia.

    `equipment`: lista de codigos de Exercise.EQUIPMENT para filtrar el
    catalogo (por ejemplo solo calistenia). None = todo el catalogo.
    """
    days_per_week = max(1, min(int(days_per_week), 6))
    scheme = GOAL_SCHEME.get(goal, GOAL_SCHEME['hipertrofia'])
    delta = LEVEL_DELTA.get(level, 0)

    if replace:
        RoutineItem.objects.filter(user=user).delete()

    # Catalogo agrupado por zona
    catalog = {}
    query = Exercise.objects.select_related('category')
    if equipment:
        query = query.filter(equipment__in=equipment)
    for ex in query:
        catalog.setdefault(ex.category.name, []).append(ex)

    cardio_pool = [e for e in query if e.kind == 'cardio']
    used = set()
    summary = []

    for index, (label, blocks) in enumerate(SPLITS[days_per_week]):
        day = WEEK_DAYS[days_per_week][index]
        order = 0
        created = []

        for zone, count in blocks:
            pool = [e for e in catalog.get(zone, []) if e.kind != 'cardio']
            if not pool:
                continue
            for ex in _pick(pool, max(1, count + delta), used):
                sets = max(2, scheme['sets'] + (1 if level == 'advanced' else 0))
                created.append(RoutineItem(
                    user=user, exercise=ex, day=day, order=order,
                    weight=0, sets=sets, reps=scheme['reps'],
                    rest_seconds=scheme['rest'],
                ))
                order += 1

        # Cardio al final para objetivos que lo necesitan
        if cardio_pool and goal in ('perder_grasa', 'resistencia'):
            ex = random.choice(cardio_pool)
            created.append(RoutineItem(
                user=user, exercise=ex, day=day, order=order,
                duration_min=scheme['cardio_min'], rest_seconds=60,
            ))

        RoutineItem.objects.bulk_create(created)
        summary.append({'day': day, 'label': label, 'count': len(created)})

    return summary
