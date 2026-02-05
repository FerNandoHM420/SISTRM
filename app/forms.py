from django import forms
from django.contrib.auth.forms import UserCreationForm, AuthenticationForm
from django.contrib.auth import get_user_model
from django.utils.translation import gettext_lazy as _
from .models import BalancinIndividual, TipoBalancin

Usuario = get_user_model()

# ========== FORMULARIOS DE AUTENTICACIÓN ==========
class RegistroForm(UserCreationForm):
    email = forms.EmailField(
        label=_('Email'),
        widget=forms.EmailInput(attrs={
            'class': 'form-control',
            'placeholder': 'ejemplo@correo.com'
        })
    )
    
    nombre = forms.CharField(
        label=_('Nombre completo'),
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Juan Pérez'
        })
    )
    
    rol = forms.ChoiceField(
        label=_('Rol'),
        choices=Usuario.RolUsuario.choices,
        widget=forms.Select(attrs={'class': 'form-control'}),
        initial=Usuario.RolUsuario.TECNICO,
        required=True
    )
    
    password1 = forms.CharField(
        label=_('Contraseña'),
        widget=forms.PasswordInput(attrs={'class': 'form-control'}),
        help_text=_('Mínimo 8 caracteres')
    )
    
    password2 = forms.CharField(
        label=_('Confirmar contraseña'),
        widget=forms.PasswordInput(attrs={'class': 'form-control'})
    )
    
    class Meta:
        model = Usuario
        fields = ['email', 'nombre', 'rol', 'password1', 'password2']
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Eliminar validación de username
        if 'username' in self.fields:
            del self.fields['username']
    
    def save(self, commit=True):
        user = super().save(commit=False)
        user.email = self.cleaned_data['email']
        user.nombre = self.cleaned_data['nombre']
        user.rol = self.cleaned_data['rol']
        if commit:
            user.save()
        return user

class LoginForm(AuthenticationForm):
    username = forms.EmailField(
        label=_('Email'),
        widget=forms.EmailInput(attrs={
            'class': 'form-control',
            'placeholder': 'ejemplo@correo.com'
        })
    )
    
    password = forms.CharField(
        label=_('Contraseña'),
        widget=forms.PasswordInput(attrs={'class': 'form-control'})
    )
    
    error_messages = {
        'invalid_login': _(
            "Por favor, introduce un email y contraseña correctos."
        ),
        'inactive': _("Esta cuenta está inactiva."),
    }
    
    def confirm_login_allowed(self, user):
        if not user.is_active:
            raise forms.ValidationError(
                self.error_messages['inactive'],
                code='inactive',
            )

# ========== FORMULARIOS DE INVENTARIO ==========
class BalancinIndividualForm(forms.ModelForm):
    class Meta:
        model = BalancinIndividual
        fields = ['serial', 'tipo', 'estado', 'ubicacion_actual', 'observaciones']
        widgets = {
            'serial': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Ej: BAL-001'
            }),
            'tipo': forms.Select(attrs={'class': 'form-select'}),
            'estado': forms.Select(attrs={'class': 'form-select'}),
            'ubicacion_actual': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Ubicación en el taller'
            }),
            'observaciones': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 3,
                'placeholder': 'Observaciones adicionales...'
            }),
        }
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Ordenar tipos por código
        self.fields['tipo'].queryset = TipoBalancin.objects.all().order_by('codigo')
        # Estado inicial siempre "taller"
        self.fields['estado'].initial = 'taller'

class CambiarEstadoForm(forms.Form):
    NUEVO_ESTADO = [
        ('taller', 'En taller'),
        ('servicio', 'En servicio'),
        ('mantenimiento', 'En mantenimiento'),
        ('baja', 'Dado de baja'),
    ]
    
    nuevo_estado = forms.ChoiceField(
        label='Nuevo estado',
        choices=NUEVO_ESTADO,
        widget=forms.Select(attrs={'class': 'form-select'})
    )
    observaciones = forms.CharField(
        label='Observaciones',
        required=False,
        widget=forms.Textarea(attrs={
            'class': 'form-control',
            'rows': 3,
            'placeholder': 'Motivo del cambio de estado...'
        })
    )

class TipoBalancinForm(forms.ModelForm):
    class Meta:
        model = TipoBalancin
        fields = ['codigo', 'tipo', 'cantidad_total']
        widgets = {
            'codigo': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Ej: 4T-501C'
            }),
            'tipo': forms.Select(attrs={'class': 'form-select'}),
            'cantidad_total': forms.NumberInput(attrs={
                'class': 'form-control',
                'min': 0
            }),
        }