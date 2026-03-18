from django.core.management.base import BaseCommand
from ...services.notificaciones_email import ServicioNotificacionesEmail
from ...models import AlertaOH

class Command(BaseCommand):
    help = 'Envía notificaciones por email para alertas pendientes'
    
    def add_arguments(self, parser):
        parser.add_argument(
            '--nivel',
            type=str,
            choices=['ROJO', 'NARANJA', 'AMARILLO', 'VENCIDO'],
            help='Nivel de alerta a notificar'
        )
        parser.add_argument(
            '--limite',
            type=int,
            default=50,
            help='Límite de alertas a procesar'
        )
    
    def handle(self, *args, **options):
        self.stdout.write('📧 Enviando notificaciones por email...')
        
        # Filtrar alertas
        alertas = AlertaOH.objects.filter(resuelta=False)
        if options['nivel']:
            alertas = alertas.filter(nivel=options['nivel'])
        
        alertas = alertas[:options['limite']]
        
        if not alertas:
            self.stdout.write(self.style.WARNING('No hay alertas para notificar'))
            return
        
        enviadas = ServicioNotificacionesEmail.notificar_alertas_criticas(alertas)
        
        self.stdout.write(self.style.SUCCESS(
            f'✅ {enviadas} notificaciones enviadas de {len(alertas)} alertas procesadas'
        ))