# apps/balancines/services/alertas_oh.py

from django.utils import timezone
from datetime import timedelta
from django.core.mail import send_mail
from django.conf import settings
import logging

logger = logging.getLogger(__name__)


class ServicioAlertasOH:
    """
    Servicio para generar y gestionar alertas de OverHaul
    """
    
    UMBRAL_ALERTA = 5000
    
    @classmethod
    def determinar_nivel(cls, backlog):
        """
        Determina el nivel de alerta según el backlog
        """
        if backlog is None:
            return None
        elif backlog < 0:
            return 'VENCIDO'
        elif backlog <= 50:
            return 'CRITICO'
        elif backlog <= 2000:
            return 'ALERTA'
        else:
            return 'VERDE'
    
    @classmethod
    def obtener_ultimo_historial(cls, balancin):
        """
        Obtiene el último registro de historial OH del balancín
        """
        from apps.balancines.models import HistorialOH
        return HistorialOH.objects.filter(
            balancin=balancin
        ).order_by('-fecha_oh').first()
    
    @classmethod
    def _enviar_email_inmediato(cls, alerta):
        """
        Envía email INMEDIATAMENTE cuando se crea una alerta
        """
        try:
            from django.core.mail import send_mail
            from django.conf import settings
            from django.utils import timezone
            
            balancin = alerta.balancin
            torre = balancin.torre
            
            # Mapeo de niveles
            if alerta.nivel == 'CRITICO':
                emoji = '🔴'
                asunto = f'{emoji} ALERTA CRÍTICA: {balancin.codigo}'
            elif alerta.nivel == 'ALERTA':
                emoji = '🟡'
                asunto = f'{emoji} ALERTA: {balancin.codigo}'
            elif alerta.nivel == 'VENCIDO':
                emoji = '🟠'
                asunto = f'{emoji} ALERTA VENCIDA: {balancin.codigo}'
            else:
                emoji = '⚠️'
                asunto = f'{emoji} Alerta: {balancin.codigo}'
            
            # Construir mensaje
            mensaje = f"""
{alerta.nivel} - {balancin.codigo}
{'=' * 50}

📊 Backlog: {alerta.backlog_momento} horas
⏱️ Horas operación: {alerta.horas_operacion_momento} horas
📍 Ubicación: {torre.linea.nombre if torre else 'N/A'} - Torre {torre.numero_torre if torre else 'N/A'}
⬆️ Sentido: {balancin.get_sentido_display()}
📅 Rango OH: {balancin.rango_horas_cambio_oh} horas

{'=' * 50}
🔗 Ver detalles: {settings.SITE_URL}/dashboard-alertas/

Este es un mensaje automático del Sistema TRM
Fecha: {timezone.now().strftime('%d/%m/%Y %H:%M:%S')}
            """
            
            # Destinatarios
            destinatarios = ['miguefernandohuanca@gmail.com']
            
            # Enviar email
            resultado = send_mail(
                subject=asunto,
                message=mensaje,
                from_email=settings.DEFAULT_FROM_EMAIL,
                recipient_list=destinatarios,
                fail_silently=False,
            )
            
            if resultado == 1:
                print(f"✅ Email enviado para alerta {alerta.id} - {balancin.codigo}")
                return True
            return False
            
        except Exception as e:
            print(f"❌ Error enviando email: {e}")
            import traceback
            traceback.print_exc()
            return False
    
    @classmethod
    def generar_alerta_para_balancin(cls, balancin, forzar=False, enviar_email=True):
        """
        Genera una alerta para un balancín específico
        """
        from apps.balancines.models import AlertaOH
        
        ultimo_historial = cls.obtener_ultimo_historial(balancin)
        
        if not ultimo_historial:
            return None
        
        if ultimo_historial.backlog is None:
            return None
        
        backlog = ultimo_historial.backlog
        nivel = cls.determinar_nivel(backlog)
        
        if nivel not in ['VENCIDO', 'ALERTA', 'CRITICO']:
            return None
        
        # Verificar si ya existe una alerta activa
        alerta_existente = AlertaOH.objects.filter(
            balancin=balancin,
            nivel=nivel,
            resuelta=False
        ).first()
        
        if alerta_existente and not forzar:
            return alerta_existente
        
        # Calcular fecha estimada
        if backlog < 0:
            fecha_estimada = timezone.now().date()
        else:
            dias_estimados = backlog / 16
            fecha_estimada = timezone.now().date() + timedelta(days=int(dias_estimados))
        
        # Crear nueva alerta
        alerta = AlertaOH.objects.create(
            balancin=balancin,
            nivel=nivel,
            backlog_momento=backlog,
            horas_operacion_momento=ultimo_historial.horas_operacion,
            fecha_estimada_vencimiento=fecha_estimada,
            leida=False,
            resuelta=False,
            observaciones=f"Alerta generada por backlog de {backlog} horas"
        )
        
        # Enviar email si está activado
        if enviar_email:
            cls._enviar_email_inmediato(alerta)
        
        return alerta
    
    @classmethod
    def generar_todas_las_alertas(cls, forzar=False, enviar_email=True):
        """
        Genera alertas para todos los balancines
        Retorna estadísticas de las alertas generadas
        """
        from apps.balancines.models import BalancinIndividual
        
        resultados = {
            'procesados': 0,
            'alertas_generadas': 0,
            'alertas_por_nivel': {
                'VENCIDO': 0,
                'ALERTA': 0,
                'CRITICO': 0,
            },
            'errores': []
        }
        
        for balancin in BalancinIndividual.objects.all():
            try:
                resultados['procesados'] += 1
                alerta = cls.generar_alerta_para_balancin(balancin, forzar, enviar_email)
                
                if alerta:
                    resultados['alertas_generadas'] += 1
                    if alerta.nivel in resultados['alertas_por_nivel']:
                        resultados['alertas_por_nivel'][alerta.nivel] += 1
                    
            except Exception as e:
                resultados['errores'].append(f'{balancin.codigo}: {str(e)}')
                print(f"Error generando alerta para {balancin.codigo}: {e}")
        
        return resultados
    
    @classmethod
    def obtener_alertas_activas(cls, incluir_leidas=False):
        """
        Obtiene todas las alertas activas
        """
        from apps.balancines.models import AlertaOH
        
        queryset = AlertaOH.objects.filter(
            resuelta=False
        ).select_related(
            'balancin',
            'balancin__torre',
            'balancin__torre__linea'
        ).order_by('-fecha_generacion')
        
        if not incluir_leidas:
            queryset = queryset.filter(leida=False)
        
        return queryset
    
    @classmethod
    def obtener_estadisticas(cls):
        """
        Obtiene estadísticas de alertas
        """
        from apps.balancines.models import AlertaOH
        
        activas = AlertaOH.objects.filter(resuelta=False)
        
        return {
            'total_activas': activas.count(),
            'no_leidas': activas.filter(leida=False).count(),
            'por_nivel': {
                'VENCIDO': activas.filter(nivel='VENCIDO').count(),
                'ALERTA': activas.filter(nivel='ALERTA').count(),
                'CRITICO': activas.filter(nivel='CRITICO').count(),
            }
        }