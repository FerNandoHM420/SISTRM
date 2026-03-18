docker exec -it proyectonuevo-web-1 bash -c "cat > apps/balancines/signals.py << 'EOF'
from django.db.models.signals import post_save
from django.dispatch import receiver
from django.utils import timezone
from .models import FormularioReacondicionamiento, BalancinIndividual, HistorialOH
from .services.alertas_oh import ServicioAlertasOH

@receiver(post_save, sender=FormularioReacondicionamiento)
def resolver_alertas_por_mantenimiento(sender, instance, created, **kwargs):
    \"\"\"
    Cuando se guarda un formulario de mantenimiento:
    1. Resuelve todas las alertas activas del balancín
    2. Cambia el estado del balancín a OPERANDO
    3. Crea un registro de historial con horas = 0
    \"\"\"
    balancin = instance.balancin
    
    # 1. Resolver alertas
    cantidad = ServicioAlertasOH.resolver_alertas_por_mantenimiento(instance)
    
    # 2. Cambiar estado del balancín
    estado_anterior = balancin.estado
    balancin.estado = 'OPERANDO'
    balancin.observaciones_estado = f'Mantenimiento realizado - Form: {instance.codigo_formulario}'
    balancin.save()
    
    # 3. Crear registro de historial con horas = 0 (reinicio)
    HistorialOH.objects.create(
        balancin=balancin,
        horas_operacion=0,
        backlog=balancin.rango_horas_cambio_oh,  # Reinicia el contador
        fecha_oh=timezone.now().date(),
        observaciones=f'Post mantenimiento - Form: {instance.codigo_formulario}',
        # Nota: Necesitarás otros campos requeridos como linea_nombre, etc.
        # Asegúrate de completarlos según tu modelo
    )
    
    print(f'✅ {cantidad} alertas resueltas para {balancin.codigo} por mantenimiento')
EOF"