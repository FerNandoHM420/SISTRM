# apps/balancines/management/commands/inicializar_controles_horas.py

from django.core.management.base import BaseCommand
from django.utils import timezone  # ← AGREGAR ESTA IMPORTACIÓN
from apps.balancines.models import BalancinIndividual, ControlHorasBalancin, HistorialOH


class Command(BaseCommand):
    help = 'Inicializa los registros de ControlHorasBalancin para todos los balancines'
    
    def handle(self, *args, **options):
        self.stdout.write("🔄 Inicializando controles de horas para todos los balancines...")
        
        total = 0
        creados = 0
        actualizados = 0
        
        for balancin in BalancinIndividual.objects.all():
            total += 1
            
            # Obtener el último OH
            ultimo_oh = HistorialOH.objects.filter(balancin=balancin).order_by('-fecha_oh').first()
            
            if ultimo_oh:
                horas_base = ultimo_oh.horas_operacion
                fecha_base = ultimo_oh.fecha_oh
            else:
                horas_base = 0
                fecha_base = timezone.now().date()
            
            control, creado = ControlHorasBalancin.objects.get_or_create(
                balancin=balancin,
                defaults={
                    'horas_base': horas_base,
                    'fecha_base': fecha_base,
                    'ultimo_oh_relacionado': ultimo_oh,
                }
            )
            
            if creado:
                creados += 1
                self.stdout.write(f"  ✅ Creado: {balancin.codigo}")
            else:
                # Recalcular horas actuales
                control.recalcular_horas()
                control.save()
                actualizados += 1
                self.stdout.write(f"  🔄 Actualizado: {balancin.codigo}")
        
        self.stdout.write(self.style.SUCCESS(
            f"\n✅ Procesados: {total} balancines"
        ))
        self.stdout.write(f"   Nuevos controles creados: {creados}")
        self.stdout.write(f"   Controles actualizados: {actualizados}")