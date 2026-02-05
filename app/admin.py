from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from django.utils.translation import gettext_lazy as _
from .models import (
    Usuario, RegistroActividad,
    TipoBalancin, BalancinIndividual,
    RepuestoBalancin, RepuestoAdicional,
    HistorialRepuesto
)

@admin.register(Usuario)
class UsuarioAdmin(UserAdmin):
    list_display = ('email', 'nombre', 'rol', 'is_active', 'is_staff', 'fecha_registro')
    list_filter = ('rol', 'is_active', 'is_staff', 'fecha_registro')
    search_fields = ('email', 'nombre')
    ordering = ('-fecha_registro',)
    
    fieldsets = (
        (None, {'fields': ('email', 'password')}),
        (_('Información personal'), {'fields': ('nombre',)}),
        (_('Roles y permisos'), {'fields': ('rol', 'is_active', 'is_staff', 'is_superuser', 'groups', 'user_permissions')}),
        (_('Fechas importantes'), {'fields': ('last_login', 'fecha_registro', 'ultima_actividad')}),
    )
    
    add_fieldsets = (
        (None, {
            'classes': ('wide',),
            'fields': ('email', 'nombre', 'rol', 'password1', 'password2', 'is_active', 'is_staff'),
        }),
    )
    
    readonly_fields = ('last_login', 'fecha_registro', 'ultima_actividad')

@admin.register(RegistroActividad)
class RegistroActividadAdmin(admin.ModelAdmin):
    list_display = ('usuario', 'accion', 'fecha')
    list_filter = ('fecha', 'usuario')
    search_fields = ('usuario__email', 'usuario__nombre', 'accion')
    readonly_fields = ('fecha',)

# ========== ADMIN PARA INVENTARIO ==========

@admin.register(TipoBalancin)
class TipoBalancinAdmin(admin.ModelAdmin):
    list_display = ('codigo', 'tipo', 'cantidad_total', 'fecha_registro', 'en_stock')
    list_filter = ('tipo',)
    search_fields = ('codigo',)
    readonly_fields = ('fecha_registro', 'fecha_actualizacion')
    
    def en_stock(self, obj):
        return obj.en_stock
    en_stock.boolean = True
    en_stock.short_description = 'En Stock'

@admin.register(BalancinIndividual)
class BalancinIndividualAdmin(admin.ModelAdmin):
    list_display = ('serial', 'tipo', 'estado', 'ubicacion_actual', 'fecha_ingreso')
    list_filter = ('estado', 'tipo')
    search_fields = ('serial', 'tipo__codigo', 'ubicacion_actual')
    readonly_fields = ('fecha_ingreso', 'fecha_ultimo_movimiento')
    list_per_page = 20

@admin.register(RepuestoBalancin)
class RepuestoBalancinAdmin(admin.ModelAdmin):
    list_display = ('item', 'descripcion_corta', 'cantidad', 'ubicacion', 'fecha_ingreso', 'en_stock')
    search_fields = ('item', 'descripcion', 'ubicacion')
    readonly_fields = ('fecha_ingreso', 'fecha_ultimo_movimiento', 'fecha_ultima_salida')
    list_per_page = 20
    
    def descripcion_corta(self, obj):
        return obj.descripcion[:100] + '...' if len(obj.descripcion) > 100 else obj.descripcion
    descripcion_corta.short_description = 'Descripción'
    
    def en_stock(self, obj):
        return obj.en_stock
    en_stock.boolean = True
    en_stock.short_description = 'En Stock'

@admin.register(RepuestoAdicional)
class RepuestoAdicionalAdmin(admin.ModelAdmin):
    list_display = ('item', 'descripcion_corta', 'cantidad', 'ubicacion', 'fecha_ingreso', 'en_stock')
    search_fields = ('item', 'descripcion', 'ubicacion')
    readonly_fields = ('fecha_ingreso', 'fecha_ultimo_movimiento', 'fecha_ultima_salida')
    list_per_page = 20
    
    def descripcion_corta(self, obj):
        return obj.descripcion[:100] + '...' if len(obj.descripcion) > 100 else obj.descripcion
    descripcion_corta.short_description = 'Descripción'
    
    def en_stock(self, obj):
        return obj.en_stock
    en_stock.boolean = True
    en_stock.short_description = 'En Stock'

@admin.register(HistorialRepuesto)
class HistorialRepuestoAdmin(admin.ModelAdmin):
    list_display = ('repuesto', 'tipo_movimiento', 'cantidad', 'stock_restante', 'fecha_movimiento')
    list_filter = ('tipo_movimiento', 'fecha_movimiento')
    search_fields = ('repuesto__item', 'observaciones')
    readonly_fields = ('fecha_movimiento',)
    list_per_page = 50