from django.utils import timezone
from datetime import timedelta
from apps.balancines.models import BalancinIndividual, HistorialOH, AlertaOH

class ServicioAlertasOH:
    """
    Servicio para generar y gestionar alertas de OverHaul
    AHORA SINCRONIZADO con el dashboard_oh_nuevo
    """
    
    # Umbrales según el dashboard (backlog < 5000 es alerta)
    UMBRAL_ALERTA = 5000  # Todo backlog < 5000 es alerta (excepto negativo)
    
    @classmethod
    def determinar_nivel(cls, backlog):
        """
        Determina el nivel de alerta según el backlog
        """
        if backlog is None:
            return None
        elif backlog < 0:
            return 'VENCIDO'          # 🟠 Naranja - Ya pasó
        elif backlog <= 50:           # 0-500 horas (1-2 días)
            return 'CRITICO'           # 🔴 Rojo - Crítico
        elif backlog <= 2000:          # 500-2000 horas (2 semanas - 1 mes)
            return 'ALERTA'            # 🟡 Amarillo - Alerta
        else:
            return 'VERDE'             # 🟢 Verde - Normal
        
    @classmethod
    def obtener_ultimo_historial(cls, balancin):
        """
        Obtiene el último registro de historial OH del balancín
        """
        return HistorialOH.objects.filter(
            balancin=balancin
        ).order_by('-fecha_oh').first()
    
    @classmethod
    def generar_alerta_para_balancin(cls, balancin, forzar=False, enviar_email=False):
        """
        Genera una alerta para un balancín específico
        SOLO si tiene OH registrados
        """
        # Obtener último historial
        ultimo_historial = cls.obtener_ultimo_historial(balancin)
        
        # ⚠️ IMPORTANTE: Si no tiene OH, NO generar alerta
        if not ultimo_historial:
            return None
        
        # Si tiene OH pero no tiene backlog (raro, pero por seguridad)
        if ultimo_historial.backlog is None:
            return None
        
        backlog = ultimo_historial.backlog
        nivel = cls.determinar_nivel(backlog)
        
        # Solo generar alertas para VENCIDO y ALERTA (no para VERDE)
        if nivel not in ['VENCIDO', 'ALERTA','CRITICO']:
            return None
        
        # Verificar si ya existe una alerta activa del mismo nivel
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
            dias_estimados = backlog / 16  # 16 horas por día
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
            observaciones=''
        )
        
        return alerta
    
    @classmethod
    def generar_todas_las_alertas(cls, forzar=False):
        """
        Genera alertas para todos los balancines
        Retorna estadísticas de las alertas generadas
        """
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
                alerta = cls.generar_alerta_para_balancin(balancin, forzar)
                
                if alerta:
                    resultados['alertas_generadas'] += 1
                    resultados['alertas_por_nivel'][alerta.nivel] += 1
                    
            except Exception as e:
                resultados['errores'].append(f'{balancin.codigo}: {str(e)}')
        
        return resultados
    
    @classmethod
    def obtener_alertas_activas(cls, incluir_leidas=False):
        """
        Obtiene todas las alertas activas (no resueltas)
        """
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
        Obtiene estadísticas de alertas para el dashboard
        """
        activas = AlertaOH.objects.filter(resuelta=False)
        
        return {
            'total_activas': activas.count(),
            'no_leidas': activas.filter(leida=False).count(),
            'por_nivel': {
                'VENCIDO': activas.filter(nivel='VENCIDO').count(),
                'ALERTA': activas.filter(nivel='ALERTA').count(),
            },
            'criticas': activas.filter(nivel='CRITICO').count()
        }