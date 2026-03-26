# apps/balancines/signals.py

from django.db.models.signals import post_save
from django.dispatch import receiver
import logging

logger = logging.getLogger(__name__)


@receiver(post_save, sender='balancines.HistorialOH')
def actualizar_control_horas(sender, instance, created, **kwargs):
    """
    Cuando se registra un nuevo OH, actualizar el ControlHorasBalancin
    """
    if created:
        try:
            from .models import ControlHorasBalancin
            
            # Obtener o crear el registro de control
            control, creado = ControlHorasBalancin.objects.get_or_create(
                balancin=instance.balancin,
                defaults={
                    'horas_base': instance.horas_operacion,
                    'fecha_base': instance.fecha_oh,
                }
            )
            
            if not creado:
                # Actualizar la base con las nuevas horas del OH
                control.actualizar_base(
                    nuevas_horas=instance.horas_operacion,
                    nueva_fecha=instance.fecha_oh,
                    nuevo_oh=instance
                )
            
            logger.info(f"✅ Control de horas actualizado para {instance.balancin.codigo}")
            
        except Exception as e:
            logger.error(f"Error actualizando control de horas: {e}")


@receiver(post_save, sender='balancines.HistorialOH')
def generar_alerta_al_registrar_oh(sender, instance, created, **kwargs):
    """Cuando se registra un nuevo OH, generar alerta inmediata"""
    if created:
        try:
            from .services.alertas_oh import ServicioAlertasOH
            
            logger.info(f"📝 Nuevo OH registrado para {instance.balancin.codigo}")
            
            # Generar alerta basada en el control de horas
            ServicioAlertasOH.generar_alerta_para_balancin(
                instance.balancin,
                forzar=True,
                enviar_email=False
            )
        except Exception as e:
            logger.error(f"Error generando alerta: {e}")


@receiver(post_save, sender='balancines.AlertaOH')
def enviar_email_al_crear_alerta(sender, instance, created, **kwargs):
    """Cuando se crea una nueva alerta, enviar email inmediato"""
    if created:
        try:
            from .services.alertas_oh import ServicioAlertasOH
            
            logger.info(f"📧 Enviando email para nueva alerta {instance.id}")
            ServicioAlertasOH._enviar_email_inmediato(instance)
        except Exception as e:
            logger.error(f"Error enviando email: {e}")