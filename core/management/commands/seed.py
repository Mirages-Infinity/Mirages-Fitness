"""Carga datos iniciales: categorias y ejercicios de ejemplo.

Uso:  python manage.py seed
"""
from django.core.management.base import BaseCommand

from core.models import Category, Exercise

CATS = {
    'Pecho': '🫁',
    'Espalda': '🔙',
    'Hombros': '🏔️',
    'Biceps': '💪',
    'Triceps': '🦾',
    'Piernas': '🦵',
    'Abdomen': '🎯',
    'Cardio': '🏃',
}

CARDIO = [
    ('Cardio', 'Caminar', 'Caminata a paso constante. Ideal para dias de recuperacion activa.'),
    ('Cardio', 'Trotar', 'Trote suave manteniendo una conversacion posible. Mejora la resistencia.'),
    ('Cardio', 'Correr', 'Carrera a ritmo exigente. Registra tus minutos y kilometros.'),
]

EXERCISES = [
    ('Pecho', 'Press de banca', 'Acostado en el banco, baja la barra al pecho y empuja hacia arriba controlando el movimiento.'),
    ('Pecho', 'Aperturas con mancuernas', 'Acostado, abre los brazos con mancuernas hasta sentir el estiramiento y vuelve a juntar.'),
    ('Pecho', 'Flexiones', 'Cuerpo recto, baja el pecho al piso y empuja. Ideal para calentar o finalizar.'),
    ('Espalda', 'Dominadas', 'Colgado de la barra, sube hasta que el mentón pase la barra. Espalda recta.'),
    ('Espalda', 'Remo con barra', 'Inclinado con espalda recta, lleva la barra hacia el abdomen apretando los omóplatos.'),
    ('Espalda', 'Jalon al pecho', 'En polea alta, tira la barra hacia el pecho manteniendo el torso firme.'),
    ('Hombros', 'Press militar', 'De pie o sentado, empuja la barra o mancuernas por encima de la cabeza.'),
    ('Hombros', 'Elevaciones laterales', 'Con mancuernas a los costados, eleva los brazos hasta la altura de los hombros.'),
    ('Biceps', 'Curl con barra', 'De pie, codos pegados al cuerpo, sube la barra contrayendo el bíceps.'),
    ('Biceps', 'Curl martillo', 'Con mancuernas en agarre neutro, sube alternando o simultáneo.'),
    ('Triceps', 'Fondos en paralelas', 'En barras paralelas, baja flexionando codos y empuja hasta extender.'),
    ('Triceps', 'Extension en polea', 'Codos fijos al cuerpo, extiende los brazos hacia abajo en la polea alta.'),
    ('Piernas', 'Sentadillas', 'Pies al ancho de hombros, baja como si te sentaras manteniendo la espalda recta.'),
    ('Piernas', 'Prensa de piernas', 'En la máquina, empuja la plataforma sin bloquear las rodillas al extender.'),
    ('Piernas', 'Peso muerto', 'Con espalda recta, levanta la barra desde el suelo extendiendo cadera y rodillas.'),
    ('Abdomen', 'Crunch abdominal', 'Acostado, eleva el torso contrayendo el abdomen. No tires del cuello.'),
    ('Abdomen', 'Plancha', 'Apoyado en antebrazos y puntas de pies, mantén el cuerpo recto el tiempo indicado.'),
]


class Command(BaseCommand):
    help = 'Carga categorias y ejercicios de ejemplo'

    def handle(self, *args, **options):
        for name, icon in CATS.items():
            Category.objects.get_or_create(name=name, defaults={'icon': icon})
        created = 0
        for cat_name, title, desc in EXERCISES:
            cat = Category.objects.get(name=cat_name)
            _, was_created = Exercise.objects.get_or_create(
                title=title, defaults={'category': cat, 'description': desc},
            )
            created += was_created
        for cat_name, title, desc in CARDIO:
            cat = Category.objects.get(name=cat_name)
            _, was_created = Exercise.objects.get_or_create(
                title=title,
                defaults={'category': cat, 'description': desc, 'kind': 'cardio'},
            )
            created += was_created
        self.stdout.write(self.style.SUCCESS(
            f'Categorias: {Category.objects.count()} | '
            f'Ejercicios: {Exercise.objects.count()} ({created} nuevos)'
        ))
