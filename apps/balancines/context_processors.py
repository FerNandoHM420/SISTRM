# apps/balancines/context_processors.py
from .services.alertas_oh import ServicioAlertasOH
from .models import AlertaOH

def notificaciones_globales(request):
    if request.user.is_authenticated:
        # Obtener todas las alertas no leídas
        alertas_no_leidas = ServicioAlertasOH.obtener_alertas_activas(incluir_leidas=False)
        
        # Filtrar SOLO las que requieren atención (VENCIDO, CRITICO, ALERTA)
        alertas_para_notificar = [
            a for a in alertas_no_leidas 
            if a.nivel in ['VENCIDO', 'CRITICO', 'ALERTA']
        ]
        
        # Estadísticas con los nombres CORRECTOS
        total_vencido = AlertaOH.objects.filter(nivel='VENCIDO', resuelta=False, leida=False).count()
        total_critico = AlertaOH.objects.filter(nivel='CRITICO', resuelta=False, leida=False).count()
        total_alerta = AlertaOH.objects.filter(nivel='ALERTA', resuelta=False, leida=False).count()
        
        return {
            'notificaciones': alertas_para_notificar[:5],
            'total_notificaciones': total_vencido + total_critico + total_alerta,
            'total_vencido': total_vencido,
            'total_critico': total_critico,
            'total_alerta': total_alerta,
        }
    
    return {
        'notificaciones': [],
        'total_notificaciones': 0,
        'total_vencido': 0,
        'total_critico': 0,
        'total_alerta': 0,
    }