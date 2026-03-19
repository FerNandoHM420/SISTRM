# apps/balancines/context_processors.py
from .services.alertas_oh import ServicioAlertasOH
from .models import AlertaOH

def notificaciones_globales(request):
    if request.user.is_authenticated:
        # Obtener todas las alertas no leídas
        alertas_no_leidas = ServicioAlertasOH.obtener_alertas_activas(incluir_leidas=False)
        
        # Filtrar SOLO las que en dashboard serían 'critico' o 'alerta'
        # Es decir: VENCIDO, ROJO y NARANJA
        alertas_para_notificar = [
            a for a in alertas_no_leidas 
            if a.nivel in ['VENCIDO', 'ROJO', 'NARANJA']
        ]
        
        # Estadísticas
        total_vencido = AlertaOH.objects.filter(nivel='VENCIDO', resuelta=False, leida=False).count()
        total_rojo = AlertaOH.objects.filter(nivel='ROJO', resuelta=False, leida=False).count()
        total_naranja = AlertaOH.objects.filter(nivel='NARANJA', resuelta=False, leida=False).count()
        
        return {
            'notificaciones': alertas_para_notificar[:5],
            'total_notificaciones': total_vencido + total_rojo + total_naranja,
            'total_vencido': total_vencido,
            'total_rojo': total_rojo,
            'total_naranja': total_naranja,
        }
    
    return {
        'notificaciones': [],
        'total_notificaciones': 0,
        'total_vencido': 0,
        'total_rojo': 0,
        'total_naranja': 0,
    }