# apps/balancines/management/commands/regenerar_alertas.py

from django.core.management.base import BaseCommand
from apps.balancines.models import AlertaOH
from apps.balancines.services.alertas_oh import ServicioAlertasOH


class Command(BaseCommand):
    help = 'Elimina todas las alertas existentes y las regenera desde cero con envío de emails'
    
    def add_arguments(self, parser):
        parser.add_argument(
            '--confirmar',
            action='store_true',
            help='Confirma que quieres eliminar todas las alertas existentes'
        )
        parser.add_argument(
            '--no-email',
            action='store_true',
            help='No enviar emails (solo regenerar alertas en BD)'
        )
        parser.add_argument(
            '--no-input',
            action='store_true',
            help='Ejecutar sin confirmación interactiva'
        )
    
    def handle(self, *args, **options):
        self.stdout.write(self.style.WARNING('=' * 60))
        self.stdout.write(self.style.WARNING('⚠️  REGENERACIÓN DE ALERTAS ⚠️'))
        self.stdout.write(self.style.WARNING('=' * 60))
        
        # Contar alertas existentes
        total_existentes = AlertaOH.objects.count()
        self.stdout.write(f"\n📊 Alertas existentes: {total_existentes}")
        
        # Confirmar si no se pasó el flag
        if not options['confirmar']:
            self.stdout.write(self.style.ERROR('\n❌ Para eliminar todas las alertas, ejecuta con --confirmar'))
            self.stdout.write(self.style.WARNING('   Ejemplo: python manage.py regenerar_alertas --confirmar'))
            return
        
        # Confirmación adicional (excepto si es --no-input)
        if not options['no_input'] and total_existentes > 0:
            self.stdout.write(self.style.WARNING(f'\n⚠️  Se eliminarán {total_existentes} alertas existentes.'))
            confirmacion = input('¿Estás seguro? (escribe "SI" para continuar): ')
            
            if confirmacion != 'SI':
                self.stdout.write(self.style.ERROR('Operación cancelada'))
                return
        
        # Eliminar todas las alertas
        if total_existentes > 0:
            self.stdout.write('\n🗑️  Eliminando alertas existentes...')
            AlertaOH.objects.all().delete()
            self.stdout.write(self.style.SUCCESS(f'✅ {total_existentes} alertas eliminadas'))
        else:
            self.stdout.write('\n✅ No hay alertas para eliminar')
        
        # Regenerar alertas
        self.stdout.write('\n🔍 Generando nuevas alertas...')
        
        enviar_email = not options['no_email']
        
        if enviar_email:
            self.stdout.write('📧 Se enviarán emails para cada alerta generada')
        else:
            self.stdout.write('🔇 Modo silencioso: no se enviarán emails')
        
        resultados = ServicioAlertasOH.generar_todas_las_alertas(
            forzar=True,
            enviar_email=enviar_email
        )
        
        # Mostrar resultados
        self.stdout.write('\n' + '=' * 60)
        self.stdout.write('📊 RESULTADOS DE LA REGENERACIÓN')
        self.stdout.write('=' * 60)
        self.stdout.write(f'   Balancines procesados: {resultados["procesados"]}')
        self.stdout.write(f'   Alertas generadas: {resultados["alertas_generadas"]}')
        self.stdout.write(f'   Por nivel:')
        self.stdout.write(f'      🔴 CRÍTICO: {resultados["alertas_por_nivel"]["CRITICO"]}')
        self.stdout.write(f'      🟡 ALERTA: {resultados["alertas_por_nivel"]["ALERTA"]}')
        self.stdout.write(f'      🟠 VENCIDO: {resultados["alertas_por_nivel"]["VENCIDO"]}')
        
        if resultados['errores']:
            self.stdout.write(self.style.ERROR(f'\n⚠️ Errores: {len(resultados["errores"])}'))
            for error in resultados['errores'][:5]:
                self.stdout.write(f'   - {error}')
        
        self.stdout.write(self.style.SUCCESS('\n✅ Regeneración completada'))