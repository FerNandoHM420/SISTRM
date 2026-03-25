# apps/balancines/forms_taller.py

from django import forms
from .models import RegistroTallerDiario, RegistroRepuestoBalancin, RegistroRepuestoAdicional, Usuario, RepuestoBalancin, RepuestoAdicional, TipoBalancin


class RegistroTallerDiarioForm(forms.ModelForm):
    """Formulario para registrar trabajos diarios del taller"""
    
    class Meta:
        model = RegistroTallerDiario
        fields = [
            'turno', 'area', 'descripcion', 'observaciones',
            'tipo_balancin', 'cantidad_balancines', 'consumibles'
            # ⚠️ IMPORTANTE: NO incluir 'fecha' aquí
        ]
        widgets = {
            'turno': forms.Select(attrs={'class': 'form-select'}),
            'area': forms.Select(attrs={'class': 'form-select'}),
            'descripcion': forms.Textarea(attrs={'rows': 3, 'class': 'form-control', 'placeholder': 'Ej: Desarme de balancines 6T-501C para inspección...'}),
            'observaciones': forms.Textarea(attrs={'rows': 2, 'class': 'form-control', 'placeholder': 'Observaciones adicionales...'}),
            'tipo_balancin': forms.Select(attrs={'class': 'form-select'}),
            'cantidad_balancines': forms.NumberInput(attrs={'class': 'form-control', 'min': 1, 'value': 1}),
            'consumibles': forms.Textarea(attrs={'rows': 2, 'class': 'form-control', 'placeholder': 'Ej: Soldadura E7018 (2kg), Aceite hidráulico (5L), Grasa (1kg)'}),
        }
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['tipo_balancin'].queryset = TipoBalancin.objects.all().order_by('codigo')
        self.fields['tipo_balancin'].required = False
        self.fields['turno'].required = False
        self.fields['turno'].empty_label = "Seleccionar (opcional)"


class RegistroRepuestoBalancinForm(forms.ModelForm):
    """Formulario para agregar repuestos de balancín usados"""
    
    class Meta:
        model = RegistroRepuestoBalancin
        fields = ['repuesto', 'cantidad']
        widgets = {
            'repuesto': forms.Select(attrs={'class': 'form-select'}),
            'cantidad': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01', 'min': '0.01'}),
        }
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['repuesto'].queryset = RepuestoBalancin.objects.filter(cantidad__gt=0)
        self.fields['repuesto'].label = "Repuesto"
        self.fields['cantidad'].label = "Cantidad usada"


class RegistroRepuestoAdicionalForm(forms.ModelForm):
    """Formulario para agregar repuestos adicionales usados"""
    
    class Meta:
        model = RegistroRepuestoAdicional
        fields = ['repuesto', 'cantidad']
        widgets = {
            'repuesto': forms.Select(attrs={'class': 'form-select'}),
            'cantidad': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01', 'min': '0.01'}),
        }
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['repuesto'].queryset = RepuestoAdicional.objects.filter(cantidad__gt=0)
        self.fields['repuesto'].label = "Repuesto adicional"
        self.fields['cantidad'].label = "Cantidad usada"# apps/balancines/forms_taller.py

from django import forms
from .models import RegistroTallerDiario, RegistroRepuestoBalancin, RegistroRepuestoAdicional, Usuario, RepuestoBalancin, RepuestoAdicional, TipoBalancin


class RegistroTallerDiarioForm(forms.ModelForm):
    """Formulario para registrar trabajos diarios del taller"""
    
    class Meta:
        model = RegistroTallerDiario
        fields = [
            'turno', 'area', 'descripcion', 'observaciones',
            'tipo_balancin', 'cantidad_balancines', 'consumibles'
            # ⚠️ IMPORTANTE: NO incluir 'fecha' aquí
        ]
        widgets = {
            'turno': forms.Select(attrs={'class': 'form-select'}),
            'area': forms.Select(attrs={'class': 'form-select'}),
            'descripcion': forms.Textarea(attrs={'rows': 3, 'class': 'form-control', 'placeholder': 'Ej: Desarme de balancines 6T-501C para inspección...'}),
            'observaciones': forms.Textarea(attrs={'rows': 2, 'class': 'form-control', 'placeholder': 'Observaciones adicionales...'}),
            'tipo_balancin': forms.Select(attrs={'class': 'form-select'}),
            'cantidad_balancines': forms.NumberInput(attrs={'class': 'form-control', 'min': 1, 'value': 1}),
            'consumibles': forms.Textarea(attrs={'rows': 2, 'class': 'form-control', 'placeholder': 'Ej: Soldadura E7018 (2kg), Aceite hidráulico (5L), Grasa (1kg)'}),
        }
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['tipo_balancin'].queryset = TipoBalancin.objects.all().order_by('codigo')
        self.fields['tipo_balancin'].required = False
        self.fields['turno'].required = False
        self.fields['turno'].empty_label = "Seleccionar (opcional)"


class RegistroRepuestoBalancinForm(forms.ModelForm):
    """Formulario para agregar repuestos de balancín usados"""
    
    class Meta:
        model = RegistroRepuestoBalancin
        fields = ['repuesto', 'cantidad']
        widgets = {
            'repuesto': forms.Select(attrs={'class': 'form-select'}),
            'cantidad': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01', 'min': '0.01'}),
        }
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['repuesto'].queryset = RepuestoBalancin.objects.filter(cantidad__gt=0)
        self.fields['repuesto'].label = "Repuesto"
        self.fields['cantidad'].label = "Cantidad usada"


class RegistroRepuestoAdicionalForm(forms.ModelForm):
    """Formulario para agregar repuestos adicionales usados"""
    
    class Meta:
        model = RegistroRepuestoAdicional
        fields = ['repuesto', 'cantidad']
        widgets = {
            'repuesto': forms.Select(attrs={'class': 'form-select'}),
            'cantidad': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01', 'min': '0.01'}),
        }
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['repuesto'].queryset = RepuestoAdicional.objects.filter(cantidad__gt=0)
        self.fields['repuesto'].label = "Repuesto adicional"
        self.fields['cantidad'].label = "Cantidad usada"