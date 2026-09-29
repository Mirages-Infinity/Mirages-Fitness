from decimal import Decimal, ROUND_HALF_UP

from django import forms
from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth.models import User

from .models import Category, Exercise, Profile, RoutineItem, SiteConfig
from .validators import normalize_rut


def kg_from_lb(lb_value):
    """Decimal en kg con 1 decimal, sin el error de precision de los float."""
    kg = Decimal(str(lb_value)) / Decimal('2.20462')
    return kg.quantize(Decimal('0.1'), rounding=ROUND_HALF_UP)

INPUT_CLASS = (
    'w-full rounded-xl bg-zinc-900 border border-zinc-700 px-4 py-3 '
    'text-white placeholder-zinc-500 focus:outline-none focus:ring-2 '
    'focus:ring-lime-400 focus:border-transparent'
)


class RegisterForm(UserCreationForm):
    rut = forms.CharField(label='RUT', max_length=12)

    class Meta:
        model = User
        fields = ['username', 'rut', 'password1', 'password2']

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        placeholders = {
            'username': 'Nombre de usuario',
            'rut': 'RUT (ej: 12.345.678-9)',
            'password1': 'Contraseña',
            'password2': 'Repetir contraseña',
        }
        for name, field in self.fields.items():
            field.widget.attrs.update({
                'class': INPUT_CLASS,
                'placeholder': placeholders.get(name, ''),
            })

    def clean_rut(self):
        rut = normalize_rut(self.cleaned_data['rut'])
        if Profile.objects.filter(rut=rut).exists():
            raise forms.ValidationError('Ya existe una cuenta registrada con este RUT.')
        return rut

    def save(self, commit=True):
        user = super().save(commit=commit)
        if commit:
            # El perfil ya lo crea la signal: aqui solo se le asigna el RUT.
            Profile.objects.update_or_create(
                user=user, defaults={'rut': self.cleaned_data['rut']},
            )
        return user


class CategoryForm(forms.ModelForm):
    class Meta:
        model = Category
        fields = ['name', 'icon', 'color', 'order']
        widgets = {
            'name': forms.TextInput(attrs={'class': INPUT_CLASS, 'placeholder': 'Ej: Espalda'}),
            'icon': forms.TextInput(attrs={'class': INPUT_CLASS, 'placeholder': 'Ej: 💪'}),
            'color': forms.TextInput(attrs={
                'type': 'color',
                'class': 'w-full h-12 rounded-xl bg-zinc-900 border border-zinc-700 p-1',
            }),
            'order': forms.NumberInput(attrs={
                'class': INPUT_CLASS, 'min': '0', 'inputmode': 'numeric',
            }),
        }


class ExerciseForm(forms.ModelForm):
    class Meta:
        model = Exercise
        fields = ['category', 'title', 'kind', 'equipment', 'level', 'description', 'image']
        widgets = {
            'category': forms.Select(attrs={'class': INPUT_CLASS}),
            'kind': forms.Select(attrs={'class': INPUT_CLASS}),
            'equipment': forms.Select(attrs={'class': INPUT_CLASS}),
            'level': forms.Select(attrs={'class': INPUT_CLASS}),
            'title': forms.TextInput(attrs={'class': INPUT_CLASS, 'placeholder': 'Ej: Press de banca'}),
            'description': forms.Textarea(attrs={
                'class': INPUT_CLASS, 'rows': 3,
                'placeholder': 'Breve descripcion de como realizar el ejercicio',
            }),
            'image': forms.ClearableFileInput(attrs={
                'class': 'w-full text-sm text-zinc-400 file:mr-3 file:rounded-lg '
                         'file:border-0 file:bg-lime-400 file:px-4 file:py-2 '
                         'file:text-sm file:font-semibold file:text-zinc-950',
                'accept': 'image/*',
            }),
        }


class SiteConfigForm(forms.ModelForm):
    class Meta:
        model = SiteConfig
        fields = ['monthly_price', 'currency', 'trial_days', 'mp_access_token', 'mp_public_key']
        widgets = {
            'monthly_price': forms.NumberInput(attrs={
                'class': INPUT_CLASS, 'step': '0.01', 'min': '0', 'inputmode': 'decimal',
            }),
            'currency': forms.Select(attrs={'class': INPUT_CLASS}),
            'trial_days': forms.NumberInput(attrs={
                'class': INPUT_CLASS, 'min': '0', 'inputmode': 'numeric',
            }),
            'mp_access_token': forms.TextInput(attrs={
                'class': INPUT_CLASS, 'placeholder': 'APP_USR-...',
                'autocomplete': 'off',
            }),
            'mp_public_key': forms.TextInput(attrs={
                'class': INPUT_CLASS, 'placeholder': 'APP_USR-...',
                'autocomplete': 'off',
            }),
        }


REST_CHOICES = [
    (30, '30 seg'), (45, '45 seg'), (60, '1 min'), (90, '1:30 min'),
    (120, '2 min'), (150, '2:30 min'), (180, '3 min'), (240, '4 min'), (300, '5 min'),
]


KG_TO_LB = 2.20462


class RoutineItemForm(forms.ModelForm):
    """Ejercicios de fuerza: peso, series, repeticiones y descanso."""
    rest_seconds = forms.TypedChoiceField(
        label='Descanso entre series', choices=REST_CHOICES, coerce=int, initial=60,
        widget=forms.Select(attrs={'class': INPUT_CLASS}),
    )

    class Meta:
        model = RoutineItem
        fields = ['weight', 'sets', 'reps', 'rest_seconds', 'note']
        widgets = {
            'weight': forms.NumberInput(attrs={
                'class': INPUT_CLASS, 'step': '0.5', 'min': '0', 'inputmode': 'decimal',
            }),
            'sets': forms.NumberInput(attrs={
                'class': INPUT_CLASS, 'min': '1', 'inputmode': 'numeric',
            }),
            'reps': forms.NumberInput(attrs={
                'class': INPUT_CLASS, 'min': '1', 'inputmode': 'numeric',
            }),
            'note': forms.TextInput(attrs={
                'class': INPUT_CLASS, 'placeholder': 'Nota opcional (ej: agarre cerrado)',
            }),
        }

    def __init__(self, *args, unit='kg', **kwargs):
        # El peso siempre se guarda en kg; si el usuario prefiere libras,
        # el campo se muestra y se recibe en lb y se convierte al guardar.
        self.unit = unit
        super().__init__(*args, **kwargs)
        if unit == 'lb':
            self.fields['weight'].label = 'Peso (lb)'
            if self.initial.get('weight') is not None:
                self.initial['weight'] = round(float(self.initial['weight']) * KG_TO_LB, 1)

    def clean_weight(self):
        weight = self.cleaned_data['weight']
        if self.unit == 'lb':
            return kg_from_lb(weight)
        return weight


class CardioItemForm(forms.ModelForm):
    """Ejercicios de cardio: duracion y distancia."""
    class Meta:
        model = RoutineItem
        fields = ['duration_min', 'distance_km', 'note']
        widgets = {
            'duration_min': forms.NumberInput(attrs={
                'class': INPUT_CLASS, 'min': '1', 'inputmode': 'numeric',
            }),
            'distance_km': forms.NumberInput(attrs={
                'class': INPUT_CLASS, 'step': '0.1', 'min': '0', 'inputmode': 'decimal',
            }),
            'note': forms.TextInput(attrs={
                'class': INPUT_CLASS, 'placeholder': 'Nota opcional (ej: ritmo suave)',
            }),
        }

    def __init__(self, *args, unit='kg', **kwargs):
        # Acepta 'unit' para tener la misma firma que RoutineItemForm
        # (no tiene campo de peso, asi que no hace nada con el valor).
        super().__init__(*args, **kwargs)
        self.fields['duration_min'].required = True
        self.fields['duration_min'].initial = 30
        self.fields['distance_km'].required = False


class PlanWizardForm(forms.Form):
    """Preferencias para que la app arme la rutina semanal."""
    days_per_week = forms.TypedChoiceField(
        label='Dias por semana', coerce=int, initial=3,
        choices=[(i, f'{i} dia{"s" if i > 1 else ""} por semana') for i in range(1, 7)],
        widget=forms.Select(attrs={'class': INPUT_CLASS}),
    )
    goal = forms.ChoiceField(
        label='Objetivo', choices=Profile.GOALS, initial='hipertrofia',
        widget=forms.Select(attrs={'class': INPUT_CLASS}),
    )
    level = forms.ChoiceField(
        label='Nivel', choices=Profile.LEVELS, initial='beginner',
        widget=forms.Select(attrs={'class': INPUT_CLASS}),
    )
    equipment = forms.MultipleChoiceField(
        label='Equipamiento disponible', choices=Exercise.EQUIPMENT, required=False,
        widget=forms.CheckboxSelectMultiple(),
        help_text='Si no marcas nada, se usa todo el catalogo.',
    )


class QuickLogForm(forms.Form):
    """Registro suelto de un ejercicio fuera de la rutina estructurada."""
    exercise = forms.ModelChoiceField(
        label='Ejercicio', queryset=Exercise.objects.select_related('category').order_by('title'),
        widget=forms.Select(attrs={'class': INPUT_CLASS, 'id': 'id_exercise'}),
    )
    weight = forms.DecimalField(
        label='Peso', required=False, min_value=0, initial=0,
        widget=forms.NumberInput(attrs={'class': INPUT_CLASS, 'step': '0.5', 'inputmode': 'decimal'}),
    )
    sets = forms.IntegerField(
        label='Series', required=False, min_value=1, initial=3,
        widget=forms.NumberInput(attrs={'class': INPUT_CLASS, 'inputmode': 'numeric'}),
    )
    reps = forms.IntegerField(
        label='Repeticiones', required=False, min_value=1, initial=10,
        widget=forms.NumberInput(attrs={'class': INPUT_CLASS, 'inputmode': 'numeric'}),
    )
    duration_min = forms.IntegerField(
        label='Duración (min)', required=False, min_value=1,
        widget=forms.NumberInput(attrs={'class': INPUT_CLASS, 'inputmode': 'numeric'}),
    )
    distance_km = forms.DecimalField(
        label='Distancia (km)', required=False, min_value=0,
        widget=forms.NumberInput(attrs={'class': INPUT_CLASS, 'step': '0.1', 'inputmode': 'decimal'}),
    )

    def __init__(self, *args, unit='kg', **kwargs):
        self.unit = unit
        super().__init__(*args, **kwargs)
        if unit == 'lb':
            self.fields['weight'].label = 'Peso (lb)'

    def clean_weight(self):
        weight = self.cleaned_data.get('weight') or 0
        if self.unit == 'lb':
            return kg_from_lb(weight)
        return weight


class ProfileForm(forms.ModelForm):
    """Preferencias de entrenamiento del usuario."""
    default_rest = forms.TypedChoiceField(
        label='Descanso preferido', choices=REST_CHOICES, coerce=int, initial=60,
        widget=forms.Select(attrs={'class': INPUT_CLASS}),
    )

    class Meta:
        model = Profile
        fields = [
            'goal', 'level', 'days_per_week', 'default_rest', 'unit',
            'bench_1rm', 'squat_1rm', 'deadlift_1rm',
        ]
        widgets = {
            'goal': forms.Select(attrs={'class': INPUT_CLASS}),
            'level': forms.Select(attrs={'class': INPUT_CLASS}),
            'days_per_week': forms.NumberInput(attrs={
                'class': INPUT_CLASS, 'min': '1', 'max': '6', 'inputmode': 'numeric',
            }),
            'unit': forms.Select(attrs={'class': INPUT_CLASS}),
            'bench_1rm': forms.NumberInput(attrs={
                'class': INPUT_CLASS, 'step': '0.5', 'min': '0', 'inputmode': 'decimal',
                'placeholder': 'Ej: 80',
            }),
            'squat_1rm': forms.NumberInput(attrs={
                'class': INPUT_CLASS, 'step': '0.5', 'min': '0', 'inputmode': 'decimal',
                'placeholder': 'Ej: 100',
            }),
            'deadlift_1rm': forms.NumberInput(attrs={
                'class': INPUT_CLASS, 'step': '0.5', 'min': '0', 'inputmode': 'decimal',
                'placeholder': 'Ej: 120',
            }),
        }
