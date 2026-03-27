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
    AHORA BASADO EN ControlHorasBalancin (horas en vivo)
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
        elif backlog <= 5000:
            return 'ALERTA'
        else:
            return 'VERDE'
    
    @classmethod
    def obtener_control_horas(cls, balancin):
        """
        Obtiene el registro de control de horas del balancín
        """
        from apps.balancines.models import ControlHorasBalancin
        try:
            return ControlHorasBalancin.objects.get(balancin=balancin)
        except ControlHorasBalancin.DoesNotExist:
            return None
    
    @classmethod
    def _obtener_destinatarios(cls, nivel):
        """
        Obtiene los destinatarios según el nivel de alerta
        """
        from apps.balancines.models import Usuario
        
        if nivel == 'CRITICO':
            # Alertas críticas: enviar a JEFES y SUPERVISORES
            usuarios = Usuario.objects.filter(
                rol__in=['jefe', 'supervisor']
            ).values_list('email', flat=True)
        elif nivel == 'ALERTA':
            # Alertas normales: enviar a SUPERVISORES y TÉCNICOS
            usuarios = Usuario.objects.filter(
                rol__in=['supervisor', 'tecnico']
            ).values_list('email', flat=True)
        elif nivel == 'VENCIDO':
            # Alertas vencidas: enviar a TODOS
            usuarios = Usuario.objects.filter(
                rol__in=['jefe', 'supervisor', 'tecnico']
            ).values_list('email', flat=True)
        else:
            usuarios = []
        
        destinatarios = list(usuarios)
        
        # Si no hay usuarios, usar email por defecto
        if not destinatarios:
            destinatarios = ['miguefernandohuanca@gmail.com']
            print(f"⚠️ No hay usuarios registrados. Usando email por defecto")
        
        return destinatarios
    
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
            
            # Obtener destinatarios según el nivel
            destinatarios = cls._obtener_destinatarios(alerta.nivel)
            
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
            
            # Enviar email
            if destinatarios:
                resultado = send_mail(
                    subject=asunto,
                    message=mensaje,
                    from_email=settings.DEFAULT_FROM_EMAIL,
                    recipient_list=destinatarios,
                    fail_silently=False,
                )
                
                if resultado == 1:
                    print(f"✅ Email enviado a {len(destinatarios)} destinatarios para alerta {alerta.id} - {balancin.codigo}")
                    return True
                else:
                    print(f"⚠️ Email no enviado (resultado: {resultado})")
                    return False
            else:
                print(f"⚠️ No hay destinatarios para alerta {alerta.id}")
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
        BASADO EN ControlHorasBalancin (horas en vivo)
        """
        from apps.balancines.models import AlertaOH
        
        # Obtener el control de horas (estado actual)
        control = cls.obtener_control_horas(balancin)
        
        if not control:
            print(f"⚠️ {balancin.codigo} no tiene registro de control de horas")
            return None
        
        # Recalcular horas en vivo
        hoy = timezone.now().date()
        horas_actuales = control.recalcular_horas(hoy)
        backlog = control.backlog_actual
        
        print(f"📊 {balancin.codigo}: Horas actuales={horas_actuales}, Backlog={backlog}")
        
        nivel = cls.determinar_nivel(backlog)
        
        if nivel not in ['VENCIDO', 'ALERTA', 'CRITICO']:
            print(f"✅ {balancin.codigo} está en nivel {nivel} - No se genera alerta")
            return None
        
        # Verificar si ya existe una alerta activa del mismo nivel
        alerta_existente = AlertaOH.objects.filter(
            balancin=balancin,
            nivel=nivel,
            resuelta=False
        ).first()
        
        if alerta_existente and not forzar:
            print(f"⚠️ Ya existe alerta {nivel} para {balancin.codigo} (ID: {alerta_existente.id})")
            # Reenviar email aunque la alerta ya exista
            if enviar_email:
                print(f"📧 Reenviando email para alerta existente {alerta_existente.id}")
                cls._enviar_email_inmediato(alerta_existente)
            return alerta_existente
        
        # Calcular fecha estimada de vencimiento
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
            horas_operacion_momento=horas_actuales,
            fecha_estimada_vencimiento=fecha_estimada,
            leida=False,
            resuelta=False,
            observaciones=f"Alerta generada por backlog de {backlog} horas (en vivo)"
        )
        
        print(f"📢 Alerta {nivel} creada para {balancin.codigo} (ID: {alerta.id})")
        
        # Enviar email si está activado
        if enviar_email:
            cls._enviar_email_inmediato(alerta)
        
        return alerta
    
    @classmethod
    def generar_todas_las_alertas(cls, forzar=False, enviar_email=True):
        """
        Genera alertas para todos los balancines basado en ControlHorasBalancin
        """
        from apps.balancines.models import BalancinIndividual, ControlHorasBalancin
        
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
        
        print("🔍 Generando alertas basadas en ControlHorasBalancin...")
        
        for balancin in BalancinIndividual.objects.all():
            try:
                resultados['procesados'] += 1
                alerta = cls.generar_alerta_para_balancin(
                    balancin, 
                    forzar=forzar,
                    enviar_email=enviar_email
                )
                
                if alerta:
                    resultados['alertas_generadas'] += 1
                    if alerta.nivel in resultados['alertas_por_nivel']:
                        resultados['alertas_por_nivel'][alerta.nivel] += 1
                    
            except Exception as e:
                resultados['errores'].append(f'{balancin.codigo}: {str(e)}')
                print(f"❌ Error en {balancin.codigo}: {e}")
        
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