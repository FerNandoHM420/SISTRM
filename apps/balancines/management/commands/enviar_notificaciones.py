# apps/balancines/management/commands/enviar_notificaciones.py

from django.core.management.base import BaseCommand
from django.core.mail import send_mail
from django.template.loader import render_to_string
from django.conf import settings
from ...services.alertas_oh import ServicioAlertasOH
from ...models import AlertaOH
import logging

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = 'Envía notificaciones por email para alertas pendientes'
    
    def add_arguments(self, parser):
        parser.add_argument(
            '--nivel',
            type=str,
            choices=['CRITICO', 'ALERTA', 'VENCIDO'],
            help='Nivel de alerta a notificar'
        )
        parser.add_argument(
            '--limite',
            type=int,
            default=50,
            help='Límite de alertas a procesar'
        )
        parser.add_argument(
            '--inmediato',
            action='store_true',
            help='Enviar emails inmediatamente (no usar cola)'
        )
    
    def handle(self, *args, **options):
        self.stdout.write(self.style.SUCCESS('📧 Enviando notificaciones por email...'))
        
        # Filtrar alertas no resueltas
        alertas = AlertaOH.objects.filter(resuelta=False)
        
        if options['nivel']:
            alertas = alertas.filter(nivel=options['nivel'])
        
        alertas = alertas[:options['limite']]
        
        if not alertas:
            self.stdout.write(self.style.WARNING('⚠️ No hay alertas para notificar'))
            return
        
        enviadas = 0
        errores = 0
        
        for alerta in alertas:
            try:
                # Enviar email inmediato usando el servicio
                if ServicioAlertasOH._enviar_email_inmediato(alerta):
                    enviadas += 1
                    self.stdout.write(f"  ✅ Enviado: {alerta.balancin.codigo} - {alerta.nivel}")
                else:
                    errores += 1
                    self.stdout.write(self.style.ERROR(f"  ❌ Error: {alerta.balancin.codigo}"))
                    
            except Exception as e:
                errores += 1
                self.stdout.write(self.style.ERROR(f"  ❌ Error {alerta.balancin.codigo}: {str(e)}"))
        
        self.stdout.write(self.style.SUCCESS(
            f'\n✅ Notificaciones enviadas: {enviadas} de {len(alertas)} alertas procesadas'
        ))
        
        if errores > 0:
            self.stdout.write(self.style.WARNING(f'⚠️ Errores: {errores}'))