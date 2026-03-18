from django.utils import timezone
from datetime import timedelta
from apps.balancines.models import BalancinIndividual, HistorialOH, AlertaOH

from .notificaciones_email import ServicioNotificacionesEmail

class ServicioAlertasOH:
    """
    Servicio para generar y gestionar alertas de OverHaul
    """
    
    UMBRALES = {
        'ROJO': 500,
        'NARANJA': 2000,
        'AMARILLO': 5000,
        'VERDE': float('inf')
    }
    
    @classmethod
    def determinar_nivel(cls, backlog):
        if backlog <= 0:
            return 'VENCIDO'
        elif backlog <= cls.UMBRALES['ROJO']:
            return 'ROJO'
        elif backlog <= cls.UMBRALES['NARANJA']:
            return 'NARANJA'
        elif backlog <= cls.UMBRALES['AMARILLO']:
            return 'AMARILLO'
        else:
            return 'VERDE'
    
    @classmethod
    def obtener_ultimo_historial(cls, balancin):
        return HistorialOH.objects.filter(
            balancin=balancin
        ).order_by('-fecha_oh').first()
    
    @classmethod
    def calcular_fecha_estimada(cls, backlog, horas_promedio_dia=16):
        if backlog <= 0:
            return timezone.now().date()
        dias_estimados = backlog / horas_promedio_dia
        return timezone.now().date() + timedelta(days=int(dias_estimados))
    
    @classmethod
    def generar_alerta_para_balancin(cls, balancin, forzar=False, enviar_email=True):
        """
        Genera una alerta para un balancín específico
        """
        ultimo_historial = cls.obtener_ultimo_historial(balancin)
        if not ultimo_historial or ultimo_historial.backlog is None:
            return None
        
        backlog = ultimo_historial.backlog
        nivel = cls.determinar_nivel(backlog)
        
        if nivel == 'VERDE':
            return None
        
        alerta_existente = AlertaOH.objects.filter(
            balancin=balancin,
            nivel=nivel,
            resuelta=False
        ).first()
        
        if alerta_existente and not forzar:
            return alerta_existente
        
        fecha_estimada = cls.calcular_fecha_estimada(backlog)
        
        alerta = AlertaOH.objects.create(
            balancin=balancin,
            nivel=nivel,
            backlog_momento=backlog,
            horas_operacion_momento=ultimo_historial.horas_operacion,
            fecha_estimada_vencimiento=fecha_estimada,
            leida=False,
            resuelta=False,
            observaciones=''
        )
        
        # Enviar email si es crítica y está activada la opción
        if enviar_email and nivel in ['ROJO', 'VENCIDO']:
            try:
                from .notificaciones_email import ServicioNotificacionesEmail
                ServicioNotificacionesEmail.enviar_notificacion_alerta(alerta)
            except Exception as e:
                print(f"Error enviando email: {e}")
        
        return alerta
    
    @classmethod
    def generar_todas_las_alertas(cls, forzar=False):
        resultados = {
            'procesados': 0,
            'alertas_generadas': 0,
            'alertas_por_nivel': {
                'ROJO': 0,
                'NARANJA': 0,
                'AMARILLO': 0,
                'VENCIDO': 0
            },
            'errores': []
        }
        
        for balancin in BalancinIndividual.objects.all():
            try:
                resultados['procesados'] += 1
                alerta = cls.generar_alerta_para_balancin(balancin, forzar)
                if alerta:
                    resultados['alertas_generadas'] += 1
                    resultados['alertas_por_nivel'][alerta.nivel] += 1
            except Exception as e:
                resultados['errores'].append(f'{balancin.codigo}: {str(e)}')
        
        return resultados
    
    @classmethod
    def resolver_alertas_por_mantenimiento(cls, formulario):
        balancin = formulario.balancin
        alertas_activas = AlertaOH.objects.filter(
            balancin=balancin,
            resuelta=False
        )
        cantidad = alertas_activas.count()
        alertas_activas.update(
            resuelta=True,
            fecha_resolucion=timezone.now(),
            formulario_resolucion=formulario
        )
        return cantidad
    
    @classmethod
    def obtener_alertas_activas(cls, incluir_leidas=False):
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
        activas = AlertaOH.objects.filter(resuelta=False)
        return {
            'total_activas': activas.count(),
            'no_leidas': activas.filter(leida=False).count(),
            'por_nivel': {
                'ROJO': activas.filter(nivel='ROJO').count(),
                'NARANJA': activas.filter(nivel='NARANJA').count(),
                'AMARILLO': activas.filter(nivel='AMARILLO').count(),
                'VENCIDO': activas.filter(nivel='VENCIDO').count(),
            },
            'criticas': activas.filter(nivel__in=['ROJO', 'VENCIDO']).count()
        }
