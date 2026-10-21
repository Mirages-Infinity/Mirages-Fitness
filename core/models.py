from datetime import date, timedelta

from django.contrib.auth.models import User
from django.core.validators import FileExtensionValidator
from django.db import models


class Category(models.Model):
    """Zona del cuerpo: Espalda, Pecho, Hombros, Abdomen, etc."""
    name = models.CharField('Nombre', max_length=50, unique=True)
    icon = models.CharField(
        'Icono (emoji)', max_length=10, blank=True, default='💪',
        help_text='Un emoji que representa la zona del cuerpo',
    )
    color = models.CharField(
        'Color', max_length=7, default='#a3e635',
        help_text='Color de la zona en la app (hex, ej: #a3e635)',
    )
    order = models.PositiveIntegerField('Orden', default=0)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'Zona del cuerpo'
        verbose_name_plural = 'Zonas del cuerpo'
        ordering = ['order', 'name']

    def __str__(self):
        return self.name


class Exercise(models.Model):
    """Ejercicio del catalogo, creado por el administrador."""
    KINDS = [
        ('strength', 'Fuerza (peso, series y repeticiones)'),
        ('cardio', 'Cardio (minutos y distancia)'),
    ]

    EQUIPMENT = [
        ('bodyweight', 'Calistenia (peso corporal)'),
        ('barbell', 'Barra'),
        ('dumbbell', 'Mancuerna'),
        ('machine', 'Maquina'),
        ('cable', 'Polea'),
        ('kettlebell', 'Kettlebell'),
        ('band', 'Banda elastica'),
        ('other', 'Otro'),
    ]
    LEVELS = [
        ('beginner', 'Principiante'),
        ('intermediate', 'Intermedio'),
        ('advanced', 'Avanzado'),
    ]

    category = models.ForeignKey(
        Category, on_delete=models.CASCADE,
        related_name='exercises', verbose_name='Zona del cuerpo',
    )
    title = models.CharField('Titulo', max_length=100)
    description = models.TextField('Descripcion', blank=True)
    image = models.ImageField('Imagen', upload_to='exercises/', blank=True, null=True)
    video = models.FileField(
        'Video (mp4, 15 seg. max.)', upload_to='exercise_videos/', blank=True, null=True,
        validators=[FileExtensionValidator(['mp4'])],
        help_text='Video corto mostrando como se hace el ejercicio. Si hay video, se muestra en vez de la imagen.',
    )
    kind = models.CharField('Tipo', max_length=10, choices=KINDS, default='strength')
    equipment = models.CharField(
        'Equipamiento', max_length=12, choices=EQUIPMENT, default='bodyweight',
    )
    level = models.CharField('Nivel', max_length=12, choices=LEVELS, default='beginner')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'Ejercicio'
        verbose_name_plural = 'Ejercicios'
        ordering = ['title']

    def __str__(self):
        return self.title


class RoutineItem(models.Model):
    """Un ejercicio dentro de la rutina semanal del usuario, asignado a un dia."""
    DAYS = [
        (0, 'Lunes'),
        (1, 'Martes'),
        (2, 'Miercoles'),
        (3, 'Jueves'),
        (4, 'Viernes'),
        (5, 'Sabado'),
        (6, 'Domingo'),
    ]

    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='routine_items')
    exercise = models.ForeignKey(Exercise, on_delete=models.CASCADE, verbose_name='Ejercicio')
    day = models.IntegerField('Dia', choices=DAYS)
    weight = models.DecimalField('Peso (kg)', max_digits=6, decimal_places=1, default=0)
    sets = models.PositiveIntegerField('Series', default=3)
    reps = models.PositiveIntegerField('Repeticiones', default=10)
    duration_min = models.PositiveIntegerField('Duracion (min)', null=True, blank=True)
    distance_km = models.DecimalField('Distancia (km)', max_digits=6, decimal_places=2, null=True, blank=True)
    rest_seconds = models.PositiveIntegerField('Descanso entre series (seg)', default=60)
    note = models.CharField('Nota', max_length=120, blank=True)
    order = models.PositiveIntegerField('Orden', default=0)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'Ejercicio de rutina'
        verbose_name_plural = 'Ejercicios de rutina'
        ordering = ['day', 'order', 'id']

    def __str__(self):
        return f'{self.user.username} - {self.get_day_display()} - {self.exercise.title}'

    @property
    def total_sets(self):
        """Cardio se cuenta como una sola 'serie'."""
        return 1 if self.exercise.kind == 'cardio' else self.sets

    @property
    def volume_kg(self):
        return float(self.weight) * self.sets * self.reps


class RoutinePlan(models.Model):
    """Copia congelada de la rutina en un momento dado (cierre de semana o mes).

    Se crea al presionar 'Guardar semana/mes': copia los RoutineItem
    vigentes a ese momento como RoutinePlanItem, sin tocar la rutina activa
    (que el usuario sigue editando para el siguiente periodo).
    """
    PERIODS = [
        ('weekly', 'Semanal'),
        ('monthly', 'Mensual'),
    ]

    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='plans')
    period = models.CharField('Periodo', max_length=10, choices=PERIODS, default='weekly')
    label = models.CharField('Nombre', max_length=60, blank=True)
    started_at = models.DateField('Inicio')
    ended_at = models.DateField('Fin', default=date.today)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'Plan guardado'
        verbose_name_plural = 'Planes guardados'
        ordering = ['-ended_at', '-id']

    def __str__(self):
        return f'{self.user.username} - {self.label or self.get_period_display()}'

    @property
    def total_items(self):
        return len(self.items.all())


class RoutinePlanItem(models.Model):
    """Copia congelada de un RoutineItem al momento de guardar el plan."""
    plan = models.ForeignKey(RoutinePlan, on_delete=models.CASCADE, related_name='items')
    exercise = models.ForeignKey(Exercise, on_delete=models.CASCADE, verbose_name='Ejercicio')
    day = models.IntegerField('Dia', choices=RoutineItem.DAYS)
    weight = models.DecimalField('Peso (kg)', max_digits=6, decimal_places=1, default=0)
    sets = models.PositiveIntegerField('Series', default=3)
    reps = models.PositiveIntegerField('Repeticiones', default=10)
    duration_min = models.PositiveIntegerField('Duracion (min)', null=True, blank=True)
    distance_km = models.DecimalField('Distancia (km)', max_digits=6, decimal_places=2, null=True, blank=True)
    rest_seconds = models.PositiveIntegerField('Descanso entre series (seg)', default=60)
    note = models.CharField('Nota', max_length=120, blank=True)
    order = models.PositiveIntegerField('Orden', default=0)

    class Meta:
        verbose_name = 'Ejercicio de plan guardado'
        verbose_name_plural = 'Ejercicios de plan guardado'
        ordering = ['day', 'order', 'id']

    def __str__(self):
        return f'{self.plan} - {self.get_day_display()} - {self.exercise.title}'

    @property
    def total_sets(self):
        return 1 if self.exercise.kind == 'cardio' else self.sets


class WorkoutLog(models.Model):
    """Registro historico: lo que el usuario realmente hizo en una fecha."""
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='workout_logs')
    exercise = models.ForeignKey(Exercise, on_delete=models.CASCADE, verbose_name='Ejercicio')
    date = models.DateField('Fecha', auto_now_add=True)
    weight = models.DecimalField('Peso (kg)', max_digits=6, decimal_places=1, default=0)
    sets = models.PositiveIntegerField('Series', default=3)
    reps = models.PositiveIntegerField('Repeticiones', default=10)
    duration_min = models.PositiveIntegerField('Duracion (min)', null=True, blank=True)
    distance_km = models.DecimalField('Distancia (km)', max_digits=6, decimal_places=2, null=True, blank=True)

    class Meta:
        verbose_name = 'Registro de entrenamiento'
        verbose_name_plural = 'Registros de entrenamiento'
        ordering = ['-date', '-id']

    def __str__(self):
        return f'{self.user.username} - {self.date} - {self.exercise.title}'


class DailyCheck(models.Model):
    """Progreso de un ejercicio en un dia concreto (series completadas)."""
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='daily_checks')
    routine_item = models.ForeignKey(RoutineItem, on_delete=models.CASCADE, related_name='checks')
    date = models.DateField('Fecha', default=date.today)
    sets_done = models.PositiveIntegerField('Series completadas', default=0)

    class Meta:
        verbose_name = 'Check diario'
        verbose_name_plural = 'Checks diarios'
        constraints = [
            models.UniqueConstraint(fields=['routine_item', 'date'], name='unique_check_per_day'),
        ]

    def __str__(self):
        return f'{self.user.username} - {self.date} - {self.routine_item.exercise.title}'

    @property
    def is_complete(self):
        return self.sets_done >= self.routine_item.total_sets


class Profile(models.Model):
    """Identidad (RUT chileno, unico) y preferencias de entrenamiento."""
    GOALS = [
        ('hipertrofia', 'Ganar masa muscular'),
        ('fuerza', 'Ganar fuerza'),
        ('perder_grasa', 'Bajar de peso / definir'),
        ('resistencia', 'Resistencia y tonificar'),
    ]
    LEVELS = [
        ('beginner', 'Principiante'),
        ('intermediate', 'Intermedio'),
        ('advanced', 'Avanzado'),
    ]
    UNITS = [
        ('kg', 'Kilogramos (kg)'),
        ('lb', 'Libras (lb)'),
    ]
    SEX_CHOICES = [
        ('M', 'Hombre'),
        ('F', 'Mujer'),
    ]
    ACTIVITY_LEVELS = [
        ('sedentary', 'Sedentario (poco o nada de ejercicio)'),
        ('light', 'Ligero (ejercicio 1-3 dias/semana)'),
        ('moderate', 'Moderado (ejercicio 3-5 dias/semana)'),
        ('active', 'Activo (ejercicio 6-7 dias/semana)'),
        ('very_active', 'Muy activo (ejercicio intenso o trabajo fisico)'),
    ]
    ACTIVITY_MULTIPLIERS = {
        'sedentary': 1.2, 'light': 1.375, 'moderate': 1.55, 'active': 1.725, 'very_active': 1.9,
    }
    # Ajuste en kcal respecto del mantenimiento segun el objetivo ya elegido
    # (campo GOALS de mas arriba), para no pedirle al usuario un dato extra.
    GOAL_CALORIE_ADJUSTMENT = {
        'perder_grasa': -500, 'hipertrofia': 350, 'fuerza': 150, 'resistencia': 0,
    }

    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='profile')
    # Los usuarios creados antes del RUT (o por consola) pueden no tenerlo:
    # el formulario de registro si lo exige y valida su unicidad.
    rut = models.CharField('RUT', max_length=12, unique=True, null=True, blank=True)
    goal = models.CharField('Objetivo', max_length=15, choices=GOALS, default='hipertrofia')
    level = models.CharField('Nivel', max_length=12, choices=LEVELS, default='beginner')
    days_per_week = models.PositiveIntegerField('Dias por semana', default=3)
    default_rest = models.PositiveIntegerField('Descanso preferido (seg)', default=60)
    unit = models.CharField('Unidad de peso', max_length=2, choices=UNITS, default='kg')
    favorites = models.ManyToManyField(
        Exercise, blank=True, related_name='favorited_by', verbose_name='Ejercicios favoritos',
    )
    # 1RM de referencia para calcular porcentajes de trabajo (opcional).
    bench_1rm = models.DecimalField('1RM Press de banca (kg)', max_digits=6, decimal_places=1, null=True, blank=True)
    squat_1rm = models.DecimalField('1RM Sentadilla (kg)', max_digits=6, decimal_places=1, null=True, blank=True)
    deadlift_1rm = models.DecimalField('1RM Peso muerto (kg)', max_digits=6, decimal_places=1, null=True, blank=True)
    # Nutricion (opcional). age/sex/height_cm/weight_kg/activity_level alimentan
    # calculate_calorie_goal(): calorie_goal ya no se tipea a mano, se recalcula
    # solo en profile_settings() cada vez que el usuario guarda estos datos.
    age = models.PositiveIntegerField('Edad', null=True, blank=True)
    sex = models.CharField('Sexo', max_length=1, choices=SEX_CHOICES, null=True, blank=True)
    height_cm = models.PositiveIntegerField('Altura (cm)', null=True, blank=True)
    weight_kg = models.DecimalField('Peso corporal (kg)', max_digits=5, decimal_places=1, null=True, blank=True)
    activity_level = models.CharField(
        'Nivel de actividad', max_length=12, choices=ACTIVITY_LEVELS, null=True, blank=True,
    )
    calorie_goal = models.PositiveIntegerField('Meta de calorias diarias', null=True, blank=True)
    # default=True: las cuentas que ya existian al agregar este campo no
    # deben ver la bienvenida de golpe. Solo las nuevas (ver signals.py)
    # arrancan en False para mostrarsela una vez.
    onboarded = models.BooleanField('Vio la bienvenida', default=True)

    class Meta:
        verbose_name = 'Perfil'
        verbose_name_plural = 'Perfiles'

    def __str__(self):
        return f'{self.user.username} ({self.rut})'

    def calculate_calorie_goal(self):
        """Formula de Mifflin-St Jeor (gasto basal) * factor de actividad,
        ajustada segun el objetivo. Devuelve None si falta algun dato."""
        if not (self.age and self.sex and self.height_cm and self.weight_kg and self.activity_level):
            return None
        weight = float(self.weight_kg)
        bmr = 10 * weight + 6.25 * self.height_cm - 5 * self.age
        bmr += 5 if self.sex == 'M' else -161
        tdee = bmr * self.ACTIVITY_MULTIPLIERS[self.activity_level]
        calories = tdee + self.GOAL_CALORIE_ADJUSTMENT.get(self.goal, 0)
        # Piso de seguridad: no sugerir una meta por debajo de lo recomendado.
        return max(round(calories), 1200)

    @property
    def macro_goals(self):
        """Reparto estandar 30% proteina / 40% carbos / 30% grasa a partir
        de la meta de calorias, para no pedirle 4 numeros al usuario."""
        if not self.calorie_goal:
            return None
        return {
            'protein': round(self.calorie_goal * 0.30 / 4),
            'carbs': round(self.calorie_goal * 0.40 / 4),
            'fat': round(self.calorie_goal * 0.30 / 9),
        }


class SiteConfig(models.Model):
    """Configuracion global de la plataforma (singleton), editable desde el panel."""
    CURRENCIES = [
        ('ARS', 'Peso argentino (ARS)'),
        ('PYG', 'Guarani (PYG)'),
        ('BRL', 'Real (BRL)'),
        ('UYU', 'Peso uruguayo (UYU)'),
        ('CLP', 'Peso chileno (CLP)'),
        ('COP', 'Peso colombiano (COP)'),
        ('PEN', 'Sol (PEN)'),
        ('MXN', 'Peso mexicano (MXN)'),
    ]

    # codigo de plan -> (meses que acredita, nombre para mostrar)
    PLANS = {
        'monthly': (1, 'Mensual'),
        'quarterly': (3, 'Trimestral'),
        'annual': (12, 'Anual'),
    }

    monthly_price = models.DecimalField('Precio mensual', max_digits=12, decimal_places=2, default=0)
    quarterly_price = models.DecimalField('Precio trimestral (3 meses)', max_digits=12, decimal_places=2, default=0)
    annual_price = models.DecimalField('Precio anual (12 meses)', max_digits=12, decimal_places=2, default=0)
    currency = models.CharField('Moneda', max_length=3, choices=CURRENCIES, default='ARS')
    trial_days = models.PositiveIntegerField('Dias de prueba gratis', default=7)
    mp_access_token = models.CharField(
        'Access Token de Mercado Pago', max_length=255, blank=True,
        help_text='Se obtiene en Mercado Pago > Tus integraciones > Credenciales',
    )
    mp_public_key = models.CharField('Public Key de Mercado Pago', max_length=255, blank=True)
    openai_api_key = models.CharField(
        'API Key de OpenAI', max_length=255, blank=True,
        help_text='Para analizar fotos de comida (nutricion). Se obtiene en platform.openai.com > API keys.',
    )

    class Meta:
        verbose_name = 'Configuracion'
        verbose_name_plural = 'Configuracion'

    def __str__(self):
        return 'Configuracion de la plataforma'

    @classmethod
    def get(cls):
        obj, _ = cls.objects.get_or_create(pk=1)
        return obj

    def price_for(self, plan):
        return {
            'monthly': self.monthly_price,
            'quarterly': self.quarterly_price,
            'annual': self.annual_price,
        }.get(plan, 0)

    @property
    def available_plans(self):
        """Planes con precio cargado (>0), con el ahorro vs. pagar mes a mes."""
        plans = []
        for code, (months, label) in self.PLANS.items():
            price = self.price_for(code)
            if price <= 0:
                continue
            monthly_equivalent = price / months
            savings_pct = None
            if self.monthly_price > 0 and code != 'monthly':
                full_price = self.monthly_price * months
                if full_price > price:
                    savings_pct = round((1 - price / full_price) * 100)
            plans.append({
                'code': code, 'label': label, 'months': months, 'price': price,
                'monthly_equivalent': monthly_equivalent, 'savings_pct': savings_pct,
            })
        # El de mayor ahorro primero (y preseleccionado): suele ser el mejor
        # negocio tanto para el usuario como para el gimnasio.
        plans.sort(key=lambda p: p['savings_pct'] or -1, reverse=True)
        return plans

    @property
    def payments_ready(self):
        has_price = self.monthly_price > 0 or self.quarterly_price > 0 or self.annual_price > 0
        return bool(self.mp_access_token) and has_price

    @property
    def ai_ready(self):
        return bool(self.openai_api_key)


class Subscription(models.Model):
    """Estado de suscripcion de cada usuario."""
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='subscription')
    trial_ends = models.DateField('Fin de prueba gratis')
    paid_until = models.DateField('Pagado hasta', null=True, blank=True)
    exempt = models.BooleanField('Liberado de pago', default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'Suscripcion'
        verbose_name_plural = 'Suscripciones'

    def __str__(self):
        return f'{self.user.username} - activa hasta {self.active_until}'

    @property
    def active_until(self):
        """Ultima fecha con acceso (la mayor entre prueba y pago)."""
        dates = [self.trial_ends]
        if self.paid_until:
            dates.append(self.paid_until)
        return max(dates)

    @property
    def is_active(self):
        return self.exempt or date.today() <= self.active_until

    @property
    def on_trial(self):
        """En periodo de prueba y sin pago vigente."""
        if self.exempt:
            return False
        today = date.today()
        paid_ok = self.paid_until and today <= self.paid_until
        return today <= self.trial_ends and not paid_ok

    @property
    def days_left(self):
        return max((self.active_until - date.today()).days, 0)

    def add_months(self, months=1):
        """Extiende el acceso pagado. Si ya vencio, cuenta desde hoy."""
        base = date.today()
        if self.paid_until and self.paid_until > base:
            base = self.paid_until
        self.paid_until = base + timedelta(days=30 * months)
        self.save()


class Payment(models.Model):
    """Pago de suscripcion via Mercado Pago (o manual del admin)."""
    STATUS = [
        ('pending', 'Pendiente'),
        ('approved', 'Aprobado'),
        ('rejected', 'Rechazado'),
    ]

    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='payments')
    amount = models.DecimalField('Monto', max_digits=12, decimal_places=2)
    currency = models.CharField('Moneda', max_length=3, default='ARS')
    months = models.PositiveIntegerField('Meses', default=1)
    status = models.CharField('Estado', max_length=10, choices=STATUS, default='pending')
    manual = models.BooleanField('Activacion manual del admin', default=False)
    mp_preference_id = models.CharField(max_length=100, blank=True)
    mp_payment_id = models.CharField(max_length=50, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'Pago'
        verbose_name_plural = 'Pagos'
        ordering = ['-created_at']

    def __str__(self):
        return f'{self.user.username} - {self.amount} {self.currency} - {self.get_status_display()}'


class MealLog(models.Model):
    """Comida registrada por el usuario, a mano o estimada con IA desde una foto."""
    MEALS = [
        ('breakfast', 'Desayuno'),
        ('lunch', 'Almuerzo'),
        ('dinner', 'Cena'),
        ('snack', 'Snack'),
    ]

    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='meal_logs')
    date = models.DateField('Fecha', default=date.today)
    meal_type = models.CharField('Comida', max_length=10, choices=MEALS, default='snack')
    photo = models.ImageField('Foto', upload_to='meals/', blank=True, null=True)
    name = models.CharField('Nombre', max_length=150, blank=True)
    calories = models.PositiveIntegerField('Calorias', default=0)
    protein_g = models.DecimalField('Proteina (g)', max_digits=6, decimal_places=1, default=0)
    carbs_g = models.DecimalField('Carbohidratos (g)', max_digits=6, decimal_places=1, default=0)
    fat_g = models.DecimalField('Grasa (g)', max_digits=6, decimal_places=1, default=0)
    ai_estimated = models.BooleanField('Estimado por IA', default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'Comida registrada'
        verbose_name_plural = 'Comidas registradas'
        ordering = ['-date', '-created_at']

    def __str__(self):
        return f'{self.user.username} - {self.date} - {self.name or self.get_meal_type_display()}'
