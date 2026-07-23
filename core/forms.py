from django import forms
from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth.models import User

from .models import Category, Exercise, Profile, RoutineItem, SiteConfig
from .validators import normalize_rut

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
            Profile.objects.create(user=user, rut=self.cleaned_data['rut'])
        return user


class CategoryForm(forms.ModelForm):
    class Meta:
        model = Category
        fields = ['name', 'icon']
        widgets = {
            'name': forms.TextInput(attrs={'class': INPUT_CLASS, 'placeholder': 'Ej: Espalda'}),
            'icon': forms.TextInput(attrs={'class': INPUT_CLASS, 'placeholder': 'Ej: 💪'}),
        }


class ExerciseForm(forms.ModelForm):
    class Meta:
        model = Exercise
        fields = ['category', 'title', 'kind', 'description', 'image']
        widgets = {
            'category': forms.Select(attrs={'class': INPUT_CLASS}),
            'kind': forms.Select(attrs={'class': INPUT_CLASS}),
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


class RoutineItemForm(forms.ModelForm):
    """Ejercicios de fuerza: peso, series y repeticiones."""
    class Meta:
        model = RoutineItem
        fields = ['weight', 'sets', 'reps']
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
        }


class CardioItemForm(forms.ModelForm):
    """Ejercicios de cardio: duracion y distancia."""
    class Meta:
        model = RoutineItem
        fields = ['duration_min', 'distance_km']
        widgets = {
            'duration_min': forms.NumberInput(attrs={
                'class': INPUT_CLASS, 'min': '1', 'inputmode': 'numeric',
            }),
            'distance_km': forms.NumberInput(attrs={
                'class': INPUT_CLASS, 'step': '0.1', 'min': '0', 'inputmode': 'decimal',
            }),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['duration_min'].required = True
        self.fields['duration_min'].initial = 30
        self.fields['distance_km'].required = False
