# Crear el comando
from django.core.management.base import BaseCommand
from ...models import HistorialOH

class Command(BaseCommand):
    help = 'Recalcula todos los backlogs de HistorialOH basado en rango_oh_horas - horas_operacion'
    
    def add_arguments(self, parser):
        parser.add_argument(
            '--balancin',
            type=str,
            help='Recalcular solo para un balancín específico'
        )
    
    def handle(self, *args, **options):
        historiales = HistorialOH.objects.all()
        
        if options['balancin']:
            historiales = historiales.filter(balancin__codigo=options['balancin'])
        
        total = historiales.count()
        actualizados = 0
        
        self.stdout.write(f"Recalculando backlogs para {total} registros...")
        
        for h in historiales:
            if h.horas_operacion is not None and h.rango_oh_horas:
                nuevo_backlog = h.rango_oh_horas - h.horas_operacion
                if h.backlog != nuevo_backlog:
                    self.stdout.write(f"  ID {h.id}: {h.backlog} → {nuevo_backlog} (rango={h.rango_oh_horas}, horas={h.horas_operacion})")
                    h.backlog = nuevo_backlog
                    h.save(update_fields=['backlog'])
                    actualizados += 1
        
        self.stdout.write(self.style.SUCCESS(
            f"✅ {actualizados} backlogs actualizados de {total} registros"
        ))
