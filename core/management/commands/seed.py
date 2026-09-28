"""Carga el catalogo completo: zonas del cuerpo y ejercicios.

Uso:  python manage.py seed
Es idempotente: no duplica lo que ya existe, solo agrega lo que falta.
"""
from django.core.management.base import BaseCommand

from core.models import Category, Exercise

# nombre: (emoji, color, orden)
CATS = {
    'Pecho':    ('🎽', '#f97316', 1),
    'Espalda':  ('🦅', '#3b82f6', 2),
    'Hombros':  ('🏔️', '#eab308', 3),
    'Biceps':   ('💪', '#a855f7', 4),
    'Triceps':  ('🦾', '#ec4899', 5),
    'Piernas':  ('🦵', '#22c55e', 6),
    'Gluteos':  ('🍑', '#ef4444', 7),
    'Abdomen':  ('🎯', '#06b6d4', 8),
    'Cardio':   ('🏃', '#a3e635', 9),
}

# (zona, titulo, equipamiento, nivel, descripcion)
EXERCISES = [
    # ---------------------------------------------------------- Pecho
    ('Pecho', 'Press de banca', 'barbell', 'intermediate', 'Acostado en el banco, baja la barra al pecho y empuja hacia arriba sin rebotar.'),
    ('Pecho', 'Press inclinado con barra', 'barbell', 'intermediate', 'Banco a 30-45 grados. Trabaja la parte alta del pecho.'),
    ('Pecho', 'Press plano con mancuernas', 'dumbbell', 'beginner', 'Permite mayor rango que la barra. Baja hasta sentir el estiramiento.'),
    ('Pecho', 'Press inclinado con mancuernas', 'dumbbell', 'beginner', 'Banco inclinado, codos a 45 grados del torso.'),
    ('Pecho', 'Aperturas con mancuernas', 'dumbbell', 'beginner', 'Brazos casi extendidos, abre en arco amplio y junta arriba.'),
    ('Pecho', 'Cruce de poleas', 'cable', 'intermediate', 'Cruza las manos al frente apretando el pecho un segundo.'),
    ('Pecho', 'Press en maquina', 'machine', 'beginner', 'Ideal para principiantes: recorrido guiado y seguro.'),
    ('Pecho', 'Peck deck (contractora)', 'machine', 'beginner', 'Junta los brazos al frente controlando la vuelta.'),
    ('Pecho', 'Flexiones de brazos', 'bodyweight', 'beginner', 'Cuerpo recto, baja el pecho al piso y empuja.'),
    ('Pecho', 'Flexiones con manos elevadas', 'bodyweight', 'beginner', 'Manos en un banco: version mas facil para empezar.'),
    ('Pecho', 'Fondos en paralelas (pecho)', 'bodyweight', 'advanced', 'Inclina el torso adelante para cargar mas el pecho.'),
    ('Pecho', 'Pullover con mancuerna', 'dumbbell', 'intermediate', 'Acostado, lleva la mancuerna por detras de la cabeza y vuelve.'),

    # ---------------------------------------------------------- Espalda
    ('Espalda', 'Dominadas', 'bodyweight', 'advanced', 'Agarre prono. Sube hasta pasar el menton por la barra.'),
    ('Espalda', 'Dominadas supinas', 'bodyweight', 'intermediate', 'Palmas hacia ti: participa mas el biceps, algo mas facil.'),
    ('Espalda', 'Jalon al pecho', 'cable', 'beginner', 'En polea alta, tira la barra al pecho con el torso firme.'),
    ('Espalda', 'Jalon agarre cerrado', 'cable', 'beginner', 'Agarre en V, codos pegados al cuerpo.'),
    ('Espalda', 'Remo con barra', 'barbell', 'intermediate', 'Torso inclinado y espalda recta, lleva la barra al abdomen.'),
    ('Espalda', 'Remo con mancuerna a una mano', 'dumbbell', 'beginner', 'Apoyado en el banco, tira del codo hacia atras.'),
    ('Espalda', 'Remo en maquina sentado', 'machine', 'beginner', 'Pecho apoyado, aprieta los omoplatos al final.'),
    ('Espalda', 'Remo en polea baja', 'cable', 'beginner', 'Sentado, espalda recta, lleva el agarre al ombligo.'),
    ('Espalda', 'Peso muerto', 'barbell', 'advanced', 'Espalda recta, empuja el piso con las piernas y extiende la cadera.'),
    ('Espalda', 'Pull-over en polea', 'cable', 'intermediate', 'Brazos rectos, baja la barra en arco hasta los muslos.'),
    ('Espalda', 'Hiperextensiones', 'bodyweight', 'beginner', 'Fortalece la zona lumbar. Sube hasta alinear el cuerpo.'),
    ('Espalda', 'Remo invertido en barra', 'bodyweight', 'beginner', 'Barra a la altura de la cadera, cuerpo recto, tira el pecho a la barra.'),

    # ---------------------------------------------------------- Hombros
    ('Hombros', 'Press militar con barra', 'barbell', 'intermediate', 'De pie, empuja la barra sobre la cabeza sin arquear la espalda.'),
    ('Hombros', 'Press de hombros con mancuernas', 'dumbbell', 'beginner', 'Sentado con respaldo, sube hasta casi juntar las mancuernas.'),
    ('Hombros', 'Press Arnold', 'dumbbell', 'intermediate', 'Empieza con palmas hacia ti y gira mientras subes.'),
    ('Hombros', 'Elevaciones laterales', 'dumbbell', 'beginner', 'Sube hasta la altura del hombro, codos levemente flexionados.'),
    ('Hombros', 'Elevaciones frontales', 'dumbbell', 'beginner', 'Sube al frente hasta la altura de los ojos, sin impulso.'),
    ('Hombros', 'Pajaros (deltoide posterior)', 'dumbbell', 'beginner', 'Torso inclinado, abre los brazos en cruz.'),
    ('Hombros', 'Face pull', 'cable', 'intermediate', 'Tira la cuerda hacia la cara separando las manos. Cuida tus hombros.'),
    ('Hombros', 'Press de hombros en maquina', 'machine', 'beginner', 'Recorrido guiado, perfecto para aprender el patron.'),
    ('Hombros', 'Encogimientos (trapecio)', 'dumbbell', 'beginner', 'Sube los hombros hacia las orejas y aguanta un segundo.'),
    ('Hombros', 'Remo al menton', 'barbell', 'intermediate', 'Sube la barra pegada al cuerpo hasta el pecho, codos altos.'),
    ('Hombros', 'Pike push-up', 'bodyweight', 'intermediate', 'Cadera alta en V invertida, baja la cabeza al piso.'),
    ('Hombros', 'Elevacion lateral con banda', 'band', 'beginner', 'Pisa la banda y abre los brazos a los costados.'),

    # ---------------------------------------------------------- Biceps
    ('Biceps', 'Curl con barra', 'barbell', 'beginner', 'Codos pegados al cuerpo, sube sin balancear el torso.'),
    ('Biceps', 'Curl con barra Z', 'barbell', 'beginner', 'La barra Z es mas amable con las munecas.'),
    ('Biceps', 'Curl con mancuernas alterno', 'dumbbell', 'beginner', 'Sube una a la vez girando la muneca al subir.'),
    ('Biceps', 'Curl martillo', 'dumbbell', 'beginner', 'Agarre neutro (palmas enfrentadas): trabaja el braquial.'),
    ('Biceps', 'Curl concentrado', 'dumbbell', 'beginner', 'Sentado, codo apoyado en el muslo. Maxima contraccion.'),
    ('Biceps', 'Curl predicador (Scott)', 'machine', 'intermediate', 'Brazos apoyados en el banco inclinado, sin trampa.'),
    ('Biceps', 'Curl en polea', 'cable', 'beginner', 'Tension constante en todo el recorrido.'),
    ('Biceps', 'Curl inclinado en banco', 'dumbbell', 'intermediate', 'Banco a 45 grados, brazos colgando: gran estiramiento.'),
    ('Biceps', 'Curl arana', 'dumbbell', 'intermediate', 'Pecho apoyado en banco inclinado, brazos perpendiculares.'),
    ('Biceps', 'Curl 21', 'barbell', 'advanced', '7 reps abajo + 7 arriba + 7 completas. Quema garantizada.'),
    ('Biceps', 'Curl con banda elastica', 'band', 'beginner', 'Ideal para entrenar en casa o para calentar.'),

    # ---------------------------------------------------------- Triceps
    ('Triceps', 'Fondos en paralelas', 'bodyweight', 'advanced', 'Torso vertical para cargar el triceps. Baja controlado.'),
    ('Triceps', 'Fondos en banco', 'bodyweight', 'beginner', 'Manos en el banco detras tuyo, baja flexionando codos.'),
    ('Triceps', 'Extension en polea alta', 'cable', 'beginner', 'Codos fijos al cuerpo, extiende hasta abajo.'),
    ('Triceps', 'Extension con cuerda', 'cable', 'beginner', 'Separa la cuerda al final del movimiento.'),
    ('Triceps', 'Press frances', 'barbell', 'intermediate', 'Acostado, baja la barra hacia la frente y extiende.'),
    ('Triceps', 'Extension sobre la cabeza', 'dumbbell', 'beginner', 'Una mancuerna con ambas manos por detras de la cabeza.'),
    ('Triceps', 'Patada de triceps', 'dumbbell', 'beginner', 'Torso inclinado, brazo pegado, extiende hacia atras.'),
    ('Triceps', 'Press cerrado', 'barbell', 'intermediate', 'Press de banca con las manos al ancho de hombros.'),
    ('Triceps', 'Extension en maquina', 'machine', 'beginner', 'Movimiento guiado, ideal para cerrar el entrenamiento.'),
    ('Triceps', 'Flexiones diamante', 'bodyweight', 'intermediate', 'Manos juntas formando un diamante bajo el pecho.'),
    ('Triceps', 'Extension con banda', 'band', 'beginner', 'Ancla la banda arriba y extiende los codos.'),

    # ---------------------------------------------------------- Piernas
    ('Piernas', 'Sentadilla con barra', 'barbell', 'intermediate', 'Pies al ancho de hombros, baja hasta romper la paralela.'),
    ('Piernas', 'Sentadilla frontal', 'barbell', 'advanced', 'Barra al frente: mas cuadriceps y mucho core.'),
    ('Piernas', 'Prensa de piernas', 'machine', 'beginner', 'Empuja sin bloquear las rodillas al extender.'),
    ('Piernas', 'Zancadas (lunges)', 'dumbbell', 'beginner', 'Paso largo, rodilla trasera casi al piso.'),
    ('Piernas', 'Sentadilla bulgara', 'dumbbell', 'intermediate', 'Pie trasero en el banco. Brutal para pierna y gluteo.'),
    ('Piernas', 'Peso muerto rumano', 'barbell', 'intermediate', 'Piernas casi rectas, baja la barra pegada a los muslos.'),
    ('Piernas', 'Extension de cuadriceps', 'machine', 'beginner', 'Extiende las rodillas y aprieta arriba.'),
    ('Piernas', 'Curl femoral', 'machine', 'beginner', 'Flexiona las rodillas llevando el talon al gluteo.'),
    ('Piernas', 'Elevacion de talones', 'machine', 'beginner', 'Gemelos: sube lo mas alto posible y baja lento.'),
    ('Piernas', 'Sentadilla goblet', 'kettlebell', 'beginner', 'Pesa contra el pecho: ensena la tecnica de sentadilla.'),
    ('Piernas', 'Sentadilla con salto', 'bodyweight', 'intermediate', 'Explosiva. Aterriza suave flexionando rodillas.'),
    ('Piernas', 'Hack squat', 'machine', 'intermediate', 'Sentadilla guiada en maquina inclinada.'),
    ('Piernas', 'Sentadilla al aire', 'bodyweight', 'beginner', 'Sin peso, perfecta para calentar o entrenar en casa.'),

    # ---------------------------------------------------------- Gluteos
    ('Gluteos', 'Hip thrust', 'barbell', 'intermediate', 'Espalda alta en el banco, empuja la cadera arriba y aprieta.'),
    ('Gluteos', 'Puente de gluteos', 'bodyweight', 'beginner', 'Acostado, eleva la cadera hasta alinear el cuerpo.'),
    ('Gluteos', 'Patada de gluteo en polea', 'cable', 'beginner', 'Lleva la pierna atras con la rodilla algo flexionada.'),
    ('Gluteos', 'Abduccion en maquina', 'machine', 'beginner', 'Abre las piernas contra la resistencia y vuelve lento.'),
    ('Gluteos', 'Peso muerto sumo', 'barbell', 'intermediate', 'Pies muy abiertos, punteras afuera: mas gluteo y aductor.'),
    ('Gluteos', 'Step up al cajon', 'dumbbell', 'beginner', 'Sube a un cajon empujando con el talon.'),
    ('Gluteos', 'Patada de burro', 'bodyweight', 'beginner', 'En cuatro apoyos, eleva la pierna manteniendo 90 grados.'),
    ('Gluteos', 'Caminata lateral con banda', 'band', 'beginner', 'Banda sobre las rodillas, pasos laterales en semisentadilla.'),
    ('Gluteos', 'Kettlebell swing', 'kettlebell', 'intermediate', 'Impulso de cadera, no de brazos. Explosivo.'),
    ('Gluteos', 'Buenos dias', 'barbell', 'advanced', 'Barra en la espalda, bisagra de cadera con espalda recta.'),
    ('Gluteos', 'Zancada inversa', 'dumbbell', 'beginner', 'Paso hacia atras: mas gluteo y menos rodilla.'),

    # ---------------------------------------------------------- Abdomen
    ('Abdomen', 'Plancha', 'bodyweight', 'beginner', 'Antebrazos y puntas de pie, cuerpo recto. Aprieta el abdomen.'),
    ('Abdomen', 'Plancha lateral', 'bodyweight', 'beginner', 'De lado, cadera arriba. Trabaja los oblicuos.'),
    ('Abdomen', 'Crunch abdominal', 'bodyweight', 'beginner', 'Eleva el torso sin tirar del cuello.'),
    ('Abdomen', 'Crunch en maquina', 'machine', 'beginner', 'Permite agregar carga progresiva al abdomen.'),
    ('Abdomen', 'Elevacion de piernas colgado', 'bodyweight', 'advanced', 'Colgado de la barra, sube las piernas rectas.'),
    ('Abdomen', 'Elevacion de piernas en suelo', 'bodyweight', 'beginner', 'Acostado, sube y baja las piernas sin tocar el piso.'),
    ('Abdomen', 'Russian twist', 'dumbbell', 'intermediate', 'Sentado, gira el torso de lado a lado con peso.'),
    ('Abdomen', 'Mountain climbers', 'bodyweight', 'beginner', 'En plancha, lleva las rodillas al pecho alternando rapido.'),
    ('Abdomen', 'Rueda abdominal', 'other', 'advanced', 'Rueda hacia adelante sin arquear la espalda baja.'),
    ('Abdomen', 'Crunch en polea arrodillado', 'cable', 'intermediate', 'De rodillas, baja el codo hacia la rodilla redondeando.'),
    ('Abdomen', 'Bicicleta abdominal', 'bodyweight', 'beginner', 'Codo hacia la rodilla contraria, alternando.'),
    ('Abdomen', 'Hollow hold', 'bodyweight', 'intermediate', 'Isometrico: brazos y piernas extendidos, lumbar pegada al piso.'),

    # ---------------------------------------------------------- Cardio
    ('Cardio', 'Caminar', 'bodyweight', 'beginner', 'Caminata a paso constante. Ideal para recuperacion activa.'),
    ('Cardio', 'Trotar', 'bodyweight', 'beginner', 'Trote suave, deberias poder conversar mientras lo haces.'),
    ('Cardio', 'Correr', 'bodyweight', 'intermediate', 'Carrera a ritmo exigente. Registra minutos y kilometros.'),
    ('Cardio', 'Bicicleta estatica', 'machine', 'beginner', 'Bajo impacto para las rodillas. Ajusta la resistencia.'),
    ('Cardio', 'Eliptica', 'machine', 'beginner', 'Trabaja tren superior e inferior sin impacto.'),
    ('Cardio', 'Cinta caminadora', 'machine', 'beginner', 'Agrega inclinacion para exigir mas sin correr.'),
    ('Cardio', 'Remo ergometro', 'machine', 'intermediate', 'Cardio de cuerpo completo. Empuja con las piernas.'),
    ('Cardio', 'Saltar la cuerda', 'other', 'intermediate', 'Quema muchisimo en poco tiempo. Saltos bajos y rapidos.'),
    ('Cardio', 'Escaladora', 'machine', 'intermediate', 'Simula subir escaleras. Gluteo y piernas ardiendo.'),
    ('Cardio', 'Burpees', 'bodyweight', 'advanced', 'Flexion + salto. El clasico del acondicionamiento.'),
    ('Cardio', 'HIIT en cinta', 'machine', 'advanced', 'Intervalos: 30 seg fuerte / 60 seg suave.'),
    ('Cardio', 'Natacion', 'other', 'beginner', 'Cardio completo sin impacto articular.'),
]


class Command(BaseCommand):
    help = 'Carga las zonas del cuerpo y el catalogo completo de ejercicios'

    def handle(self, *args, **options):
        for name, (icon, color, order) in CATS.items():
            cat, _ = Category.objects.get_or_create(name=name)
            # Actualiza el estilo aunque la zona ya existiera
            cat.icon, cat.color, cat.order = icon, color, order
            cat.save()

        created = 0
        for cat_name, title, equipment, level, desc in EXERCISES:
            cat = Category.objects.get(name=cat_name)
            _, was_created = Exercise.objects.get_or_create(
                title=title,
                defaults={
                    'category': cat, 'description': desc,
                    'equipment': equipment, 'level': level,
                    'kind': 'cardio' if cat_name == 'Cardio' else 'strength',
                },
            )
            created += was_created

        self.stdout.write(self.style.SUCCESS(
            f'Zonas: {Category.objects.count()} | '
            f'Ejercicios: {Exercise.objects.count()} ({created} nuevos)'
        ))
