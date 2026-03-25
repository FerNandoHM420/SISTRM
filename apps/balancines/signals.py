# apps/balancines/signals.py

from django.db.models.signals import post_save
from django.dispatch import receiver
import logging

logger = logging.getLogger(__name__)


@receiver(post_save, sender='balancines.HistorialOH')
def generar_alerta_al_registrar_oh(sender, instance, created, **kwargs):
    """Cuando se registra un nuevo OH, generar alerta inmediata"""
    if created:
        try:
            from .services.alertas_oh import ServicioAlertasOH
            
            logger.info(f"📝 Nuevo OH registrado para {instance.balancin.codigo}")
            
            ServicioAlertasOH.generar_alerta_para_balancin(
                instance.balancin,
                forzar=True,
                enviar_email=True
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