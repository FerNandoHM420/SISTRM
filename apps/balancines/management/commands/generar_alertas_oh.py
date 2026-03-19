from django.core.management.base import BaseCommand
from django.utils import timezone
from apps.balancines.services.alertas_oh import ServicioAlertasOH

class Command(BaseCommand):
    help = 'Genera alertas de OverHaul para todos los balancines'
    
    def add_arguments(self, parser):
        parser.add_argument(
            '--balancin',
            type=str,
            help='Código de balancín específico (opcional)'
        )
        parser.add_argument(
            '--forzar',
            action='store_true',
            help='Forzar generación aunque ya existan alertas'
        )
    
    def handle(self, *args, **options):
        inicio = timezone.now()
        self.stdout.write('🔍 Generando alertas de OverHaul...')
        
        if options['balancin']:
            from apps.balancines.models import BalancinIndividual
            try:
                balancin = BalancinIndividual.objects.get(codigo=options['balancin'])
                alerta = ServicioAlertasOH.generar_alerta_para_balancin(
                    balancin, 
                    forzar=options['forzar']
                )
                if alerta:
                    self.stdout.write(
                        self.style.SUCCESS(
                            f'✅ Alerta {alerta.nivel} generada para {balancin.codigo}'
                        )
                    )
                else:
                    self.stdout.write(
                        self.style.WARNING(
                            f'⚠️ No se generó alerta para {balancin.codigo}'
                        )
                    )
            except BalancinIndividual.DoesNotExist:
                self.stdout.write(
                    self.style.ERROR(f'❌ Balancín {options["balancin"]} no encontrado')
                )
        else:
            resultados = ServicioAlertasOH.generar_todas_las_alertas(
                forzar=options['forzar']
            )
            
            duracion = (timezone.now() - inicio).total_seconds()
            
            self.stdout.write(self.style.SUCCESS(
                f'\n📊 RESULTADOS:\n'
                f'   Procesados: {resultados["procesados"]} balancines\n'
                f'   Alertas generadas: {resultados["alertas_generadas"]}\n'
                f'   Por nivel:\n'
                f'     ⚫ VENCIDAS: {resultados["alertas_por_nivel"].get("VENCIDO", 0)}\n'
                f'     🟠 ALERTAS: {resultados["alertas_por_nivel"].get("ALERTA", 0)}\n'
                f'   ⏱️  Tiempo: {duracion:.2f} segundos'
            ))
            
            if resultados['errores']:
                self.stdout.write(self.style.ERROR('\n❌ Errores:'))
                for error in resultados['errores']:
                    self.stdout.write(self.style.ERROR(f'   {error}'))