import sys
import io
# Forzar UTF-8 para la salida estándar
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
import time
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')

from django.core.mail import send_mail, EmailMultiAlternatives
from django.template.loader import render_to_string
from django.utils.html import strip_tags
from django.conf import settings
from django.utils import timezone
from ..models import Usuario, AlertaOH

class ServicioNotificacionesEmail:
    """
    Servicio para enviar notificaciones por email
    """
    
    @classmethod
    def obtener_destinatarios(cls, nivel_alerta):
        """
        Determina quiénes reciben cada tipo de alerta
        """
        if nivel_alerta in ['ROJO', 'VENCIDO']:
            usuarios = Usuario.objects.filter(
                rol__in=['jefe', 'supervisor'],
                is_active=True
            )
        elif nivel_alerta == 'NARANJA':
            usuarios = Usuario.objects.filter(
                rol='supervisor',
                is_active=True
            )
        else:
            return []
        
        emails = [u.email for u in usuarios if u.email]
        return emails
    
    @classmethod
    def enviar_notificacion_alerta(cls, alerta):
        """
        Envía email para una alerta específica
        """
        destinatarios = cls.obtener_destinatarios(alerta.nivel)
        
        if not destinatarios:
            print(f"⚠️ No hay destinatarios para alerta {alerta.nivel}")
            return False
        
        # Preparar contexto
        context = {
            'alerta': alerta,
            'balancin': alerta.balancin,
            'torre': alerta.balancin.torre,
            'linea': alerta.balancin.torre.linea,
            'sitio_url': settings.SITE_URL,
            'fecha': timezone.now().strftime('%d/%m/%Y %H:%M'),
        }
        
        # Renderizar templates
        html_message = render_to_string('emails/alerta_oh.html', context)
        plain_message = strip_tags(html_message)
        
        # Forzar codificación UTF-8
        if isinstance(plain_message, str):
            plain_message = plain_message.encode('utf-8').decode('utf-8')
        if isinstance(html_message, str):
            html_message = html_message.encode('utf-8').decode('utf-8')
        
        asunto = f'Alerta {alerta.get_nivel_display()} - Balancín {alerta.balancin.codigo}'
        if alerta.nivel == 'VENCIDO':
            asunto = f'URGENTE: {asunto}'
        
        try:
            send_mail(
                subject=asunto,
                message=plain_message,
                from_email=settings.DEFAULT_FROM_EMAIL,
                recipient_list=destinatarios,
                html_message=html_message,
                fail_silently=False,
            )
            
            print(f"✅ Email enviado para alerta {alerta.id} a {len(destinatarios)} destinatarios")
            return True
            
        except Exception as e:
            print(f"❌ Error enviando email: {e}")
            return False
    
    @classmethod
    def notificar_alertas_criticas(cls, alertas=None):
        """
        Envía notificaciones para alertas críticas con pausa entre envíos
        """
        if alertas is None:
            alertas = AlertaOH.objects.filter(
                nivel__in=['ROJO', 'VENCIDO'],
                resuelta=False
            )[:10]
        
        enviadas = 0
        for i, alerta in enumerate(alertas):
            if cls.enviar_notificacion_alerta(alerta):
                enviadas += 1
            # Pausa de 2 segundos entre cada envío (excepto el último)
            if i < len(alertas) - 1:
                time.sleep(1000)
        
        return enviadas