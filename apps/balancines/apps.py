# apps/balancines/apps.py

from django.apps import AppConfig


class BalancinesConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'apps.balancines'
    verbose_name = 'Balancines y Mantenimiento'
    
    def ready(self):
        """
        Cargar las señales cuando la app está lista
        """
        try:
            import apps.balancines.signals
        except ImportError as e:
            print(f"Error importing signals: {e}")