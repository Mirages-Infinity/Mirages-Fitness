"""Vincula los GIF ya subidos en media/gif/ con su ejercicio correspondiente.

Los archivos se suben a mano (FTP, panel de archivos de PythonAnywhere, etc.)
a media/gif/, pero el campo Exercise.image queda vacio hasta que alguien lo
asigna. Este comando hace ese enlace una vez, por nombre de archivo.
"""
from django.core.management.base import BaseCommand

from core.models import Exercise

# nombre de archivo en media/gif/ -> titulo exacto del Exercise
GIF_MAP = {
    'bicicleta-abdominal.gif': 'Bicicleta abdominal',
    'bicicleta-estatica.gif': 'Bicicleta estatica',
    'buenos-dias.gif': 'Buenos dias',
    'burpees.gif': 'Burpees',
    'caminar.gif': 'Caminar',
    'crunch-abdominal.gif': 'Crunch abdominal',
    'curl-arana.gif': 'Curl arana',
    'curl-femoral.gif': 'Curl femoral',
    'curl-martillo.gif': 'Curl martillo',
    'dominadas.gif': 'Dominadas',
    'abducion-maquina.gif': 'Abduccion en maquina',
    'apertura-mancuernas.gif': 'Aperturas con mancuernas',
    'caminata-lateral-banda.gif': 'Caminata lateral con banda',
    'carrera.gif': 'Correr',
    'carrera-cinta.gif': 'Cinta caminadora',
    'cruce-poleas.gif': 'Cruce de poleas',
    'crunch-maquina.gif': 'Crunch en maquina',
    'crunch-polea.gif': 'Crunch en polea arrodillado',
    'curl-banda.gif': 'Curl con banda elastica',
    'curl-barra.gif': 'Curl con barra',
    'curl-barra-z.gif': 'Curl con barra Z',
    'curl-inclinado-banco.gif': 'Curl inclinado en banco',
    'curl-mancuerna.gif': 'Curl con mancuernas alterno',
    'curl-polea.gif': 'Curl en polea',
    'curl-scott.gif': 'Curl predicador (Scott)',
    'curl-sentado.gif': 'Curl concentrado',
    'pec-deck.gif': 'Peck deck (contractora)',
    'dominadas-supinas.gif': 'Dominadas supinas',
    'elevacion-piernas-suelo.gif': 'Elevacion de piernas en suelo',
    'elevacion-piernas-colgado.gif': 'Elevacion de piernas colgado',
    'elevacion-talones.gif': 'Elevacion de talones',
    'elevacion-lateral-mancuernas.gif': 'Elevaciones laterales',
    # curl.gif, crunch-superior.gif y dominadas-alt.gif no se asignan:
    # no hay un ejercicio inequivoco al que correspondan (dominadas-alt.gif
    # es una segunda opcion para "Dominadas", que ya tiene dominadas.gif).
    # Asignalos a mano desde el panel si corresponde.
}


class Command(BaseCommand):
    help = 'Vincula los GIF de media/gif/ con su Exercise por nombre de archivo.'

    def add_arguments(self, parser):
        parser.add_argument(
            '--force', action='store_true',
            help='Sobreescribe la imagen aunque el ejercicio ya tenga una asignada.',
        )

    def handle(self, *args, **options):
        force = options['force']
        linked, skipped, missing = 0, 0, 0
        for filename, title in GIF_MAP.items():
            try:
                exercise = Exercise.objects.get(title=title)
            except Exercise.DoesNotExist:
                self.stdout.write(self.style.WARNING(f'[!] No existe el ejercicio "{title}" ({filename})'))
                missing += 1
                continue
            if exercise.image and not force:
                self.stdout.write(f'· "{title}" ya tiene imagen, se omite (usa --force para pisarla)')
                skipped += 1
                continue
            exercise.image.name = f'gif/{filename}'
            exercise.save(update_fields=['image'])
            self.stdout.write(self.style.SUCCESS(f'[OK] {title} -> {filename}'))
            linked += 1

        self.stdout.write(self.style.SUCCESS(
            f'\nListo: {linked} vinculados, {skipped} omitidos, {missing} sin coincidencia.'
        ))
