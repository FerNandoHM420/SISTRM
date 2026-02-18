from django import forms
from django.contrib.auth.forms import UserCreationForm, AuthenticationForm
from django.contrib.auth import get_user_model
from django.utils.translation import gettext_lazy as _
from .models import BalancinIndividual, TipoBalancin, Torre, Linea

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

# ========== FORMULARIO PARA BALANCÍN INDIVIDUAL ==========
class BalancinIndividualForm(forms.ModelForm):
    """Formulario para balancines instalados en torres"""
    
    class Meta:
        model = BalancinIndividual
        fields = ['codigo', 'torre', 'sentido', 'rango_horas_cambio_oh', 'observaciones']
        widgets = {
            'codigo': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Ej: BAL-16N/4TR-0001'
            }),
            'torre': forms.Select(attrs={
                'class': 'form-select',
            }),
            'sentido': forms.Select(attrs={
                'class': 'form-select'
            }),
            'rango_horas_cambio_oh': forms.NumberInput(attrs={
                'class': 'form-control',
                'min': 1,
                'placeholder': '30000'
            }),
            'observaciones': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 2,
                'placeholder': 'Observaciones adicionales...'
            }),
        }
        labels = {
            'codigo': 'Código/Serial del Balancín',
            'torre': 'Torre de instalación',
            'sentido': 'Sentido',
            'rango_horas_cambio_oh': 'Rango de horas para OH',
            'observaciones': 'Observaciones',
        }
        help_texts = {
            'codigo': 'Identificador único del balancín',
            'rango_horas_cambio_oh': 'Horas de operación antes de requerir mantenimiento',
        }
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Formato amigable para mostrar torres
        self.fields['torre'].queryset = Torre.objects.select_related('linea', 'seccion').all()
        self.fields['torre'].label_from_instance = lambda obj: f"L{obj.linea_id} - Torre {obj.numero_torre} (Secc: {obj.seccion.nombre})"
        
        # Si ya hay una torre seleccionada, no mostrar el queryset completo
        if self.instance and self.instance.pk:
            self.fields['torre'].disabled = True
    
    def clean_codigo(self):
        codigo = self.cleaned_data.get('codigo')
        if codigo:
            codigo = codigo.upper().strip()
            
            # Validar formato básico
            if not codigo.startswith('BAL-'):
                codigo = f"BAL-{codigo}"
            
            # Verificar si ya existe (excepto cuando se edita)
            if not self.instance.pk:
                if BalancinIndividual.objects.filter(codigo=codigo).exists():
                    raise forms.ValidationError(f'Ya existe un balancín con el código {codigo}')
        
        return codigo
    
    def clean(self):
        cleaned_data = super().clean()
        torre = cleaned_data.get('torre')
        sentido = cleaned_data.get('sentido')
        
        # Verificar que no exista ya un balancín en la misma torre con el mismo sentido
        if torre and sentido and not self.instance.pk:
            if BalancinIndividual.objects.filter(torre=torre, sentido=sentido).exists():
                raise forms.ValidationError(
                    f'Ya existe un balancín {sentido} instalado en esta torre'
                )
        
        return cleaned_data

# ========== FORMULARIO PARA SELECCIONAR TORRE POR LÍNEA ==========
class SeleccionarTorreForm(forms.Form):
    """Formulario para seleccionar una torre por línea y número"""
    
    linea = forms.ModelChoiceField(
        queryset=Linea.objects.all(),
        label='Línea',
        widget=forms.Select(attrs={
            'class': 'form-select',
            'id': 'id_linea'
        })
    )
    
    numero_torre = forms.CharField(
        label='Número de torre',
        max_length=10,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Ej: 1, 2A, 6B'
        })
    )
    
    sentido = forms.ChoiceField(
        label='Sentido',
        choices=BalancinIndividual.SentidoBalancin.choices,
        widget=forms.Select(attrs={'class': 'form-select'}),
        initial='ASCENDENTE'
    )
    
    rango_horas = forms.IntegerField(
        label='Rango de horas para OH',
        initial=30000,
        min_value=1,
        widget=forms.NumberInput(attrs={
            'class': 'form-control',
            'placeholder': '30000'
        })
    )
    
    def clean(self):
        cleaned_data = super().clean()
        linea = cleaned_data.get('linea')
        numero_torre = cleaned_data.get('numero_torre')
        
        if linea and numero_torre:
            # Buscar la torre específica
            torre = Torre.objects.filter(linea=linea, numero_torre=numero_torre).first()
            if not torre:
                raise forms.ValidationError(
                    f'No existe la torre {numero_torre} en la línea {linea.nombre}'
                )
            cleaned_data['torre'] = torre
        
        return cleaned_data


# ========== FORMULARIO PARA REGISTRAR OH ==========
class RegistrarOHForm(forms.Form):
    """Formulario para registrar órdenes de horas de balancines"""
    
    numero_oh = forms.IntegerField(
        label='Número de OH',
        min_value=1,
        widget=forms.NumberInput(attrs={
            'class': 'form-control',
            'placeholder': 'Ej: 1, 2, 3...'
        })
    )
    
    fecha_oh = forms.DateField(
        label='Fecha de OH',
        widget=forms.DateInput(attrs={
            'class': 'form-control',
            'type': 'date'
        })
    )
    
    horas_operacion = forms.IntegerField(
        label='Horas de operación',
        required=False,
        min_value=0,
        widget=forms.NumberInput(attrs={
            'class': 'form-control',
            'placeholder': 'Horas acumuladas'
        })
    )
    
    observaciones = forms.CharField(
        label='Observaciones',
        required=False,
        widget=forms.Textarea(attrs={
            'class': 'form-control',
            'rows': 2,
            'placeholder': 'Observaciones de la OH...'
        })
    )


# ========== FORMULARIO PARA TIPO DE BALANCÍN ==========
class TipoBalancinForm(forms.ModelForm):
    class Meta:
        model = TipoBalancin
        fields = ['codigo', 'tipo', 'cantidad_total']
        widgets = {
            'codigo': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Ej: 16N/4TR-420C'
            }),
            'tipo': forms.Select(attrs={'class': 'form-select'}),
            'cantidad_total': forms.NumberInput(attrs={
                'class': 'form-control',
                'min': 0
            }),
        }
        labels = {
            'codigo': 'Código del modelo',
            'tipo': 'Tipo de balancín',
            'cantidad_total': 'Cantidad total en inventario',
        }
    
    def clean_codigo(self):
        codigo = self.cleaned_data.get('codigo')
        if codigo:
            codigo = codigo.upper().strip()
        return codigo


# ========== FORMULARIO PARA CAMBIAR ESTADO ==========
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
    
    # apps/balancines/forms.py - Agrega esto al final

class NuevoOHForm(forms.Form):
    """Formulario para registrar un nuevo OH"""
    
    balancin = forms.ModelChoiceField(
        queryset=BalancinIndividual.objects.all().order_by('codigo'),
        label='Balancín',
        widget=forms.Select(attrs={
            'class': 'form-select',
            'id': 'id_balancin'
        })
    )
    
    numero_oh = forms.IntegerField(
        label='Número de OH',
        min_value=1,
        widget=forms.NumberInput(attrs={
            'class': 'form-control',
            'placeholder': 'Ej: 3, 4, 5...',
            'readonly': 'readonly'  # Se calculará automáticamente
        })
    )
    
    fecha_oh = forms.DateField(
        label='Fecha del OH',
        widget=forms.DateInput(attrs={
            'class': 'form-control datepicker',
            'type': 'date'
        })
    )
    
    horas_operacion = forms.IntegerField(
        label='Horas de operación',
        min_value=0,
        widget=forms.NumberInput(attrs={
            'class': 'form-control',
            'placeholder': 'Ej: 42000'
        })
    )
    
    observaciones = forms.CharField(
        label='Observaciones',
        required=False,
        widget=forms.Textarea(attrs={
            'class': 'form-control',
            'rows': 3,
            'placeholder': 'Observaciones del mantenimiento...'
        })
    )
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Personalizar cómo se muestran los balancines
        self.fields['balancin'].label_from_instance = self._label_from_instance
    
    def _label_from_instance(self, obj):
        """Muestra información detallada del balancín"""
        torre = obj.torre
        linea = torre.linea.nombre if torre and torre.linea else 'N/A'
        return f"{obj.codigo} - {linea} T{torre.numero_torre} ({obj.get_sentido_display()})"