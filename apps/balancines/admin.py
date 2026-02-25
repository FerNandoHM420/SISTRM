from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from django.utils.translation import gettext_lazy as _
from django.utils.html import format_html
from django.urls import reverse

from .models import (
    Usuario, RegistroActividad,
    Linea, Seccion, Torre,
    TipoBalancin, BalancinIndividual, BalancinOH, HistorialBalancin,
    RepuestoBalancin, RepuestoAdicional,
    HistorialRepuesto, HistorialAdicional,
    HistorialOH # ✅ IMPORT CORRECTO AQUÍ
)

# ========== CONFIGURACIÓN GENERAL ==========
admin.site.site_header = 'Sistema TRM - Administración'
admin.site.site_title = 'TRM Admin'
admin.site.index_title = 'Panel de Administración de Inventario'


# ========== USUARIOS ==========
@admin.register(Usuario)
class UsuarioAdmin(UserAdmin):
    list_display = ('email', 'nombre', 'rol', 'is_active', 'is_staff', 'fecha_registro')
    list_filter = ('rol', 'is_active', 'is_staff', 'fecha_registro')
    search_fields = ('email', 'nombre')
    ordering = ('-fecha_registro',)

    fieldsets = (
        (None, {'fields': ('email', 'password')}),
        (_('Información personal'), {'fields': ('nombre',)}),
        (_('Roles y permisos'), {
            'fields': ('rol', 'is_active', 'is_staff', 'is_superuser',
                       'groups', 'user_permissions')
        }),
        (_('Fechas importantes'), {
            'fields': ('last_login', 'fecha_registro', 'ultima_actividad')
        }),
    )

    add_fieldsets = (
        (None, {
            'classes': ('wide',),
            'fields': ('email', 'nombre', 'rol',
                       'password1', 'password2',
                       'is_active', 'is_staff'),
        }),
    )

    readonly_fields = ('last_login', 'fecha_registro', 'ultima_actividad')


# ========== REGISTRO ACTIVIDAD ==========
@admin.register(RegistroActividad)
class RegistroActividadAdmin(admin.ModelAdmin):
    list_display = ('usuario', 'accion', 'fecha')
    list_filter = ('fecha', 'usuario')
    search_fields = ('usuario__email', 'usuario__nombre', 'accion')
    readonly_fields = ('fecha',)


# ========== CATÁLOGOS ==========
@admin.register(Linea)
class LineaAdmin(admin.ModelAdmin):
    list_display = ('id', 'nombre', 'fecha_registro', 'cantidad_torres')
    search_fields = ('nombre',)
    readonly_fields = ('fecha_registro',)

    def cantidad_torres(self, obj):
        return obj.torres.count()
    cantidad_torres.short_description = 'Cantidad de Torres'


@admin.register(Seccion)
class SeccionAdmin(admin.ModelAdmin):
    list_display = ('id', 'nombre')
    search_fields = ('nombre',)


@admin.register(Torre)
class TorreAdmin(admin.ModelAdmin):
    list_display = (
        'id', 'linea', 'numero_torre', 'seccion',
        'tipo_balancin_ascendente',
        'tipo_balancin_descendente',
        'balancines_instalados'
    )
    list_filter = ('linea', 'seccion')
    search_fields = (
        'numero_torre', 'linea__nombre',
        'tipo_balancin_ascendente',
        'tipo_balancin_descendente'
    )
    readonly_fields = ('fecha_registro',)

    def balancines_instalados(self, obj):
        count = obj.balancines.count()
        if count > 0:
            return format_html(
                '<span style="color: green; font-weight: bold;">{} instalado{}</span>',
                count, 's' if count > 1 else ''
            )
        return format_html('<span style="color: gray;">0 instalados</span>')
    balancines_instalados.short_description = 'Balancines'


# ========== TIPO BALANCÍN ==========
@admin.register(TipoBalancin)
class TipoBalancinAdmin(admin.ModelAdmin):
    list_display = (
        'codigo', 'tipo', 'cantidad_total',
        'fecha_registro', 'en_stock',
        'balancines_instalados'
    )
    list_filter = ('tipo',)
    search_fields = ('codigo',)
    readonly_fields = ('fecha_registro', 'fecha_actualizacion')

    def en_stock(self, obj):
        return obj.en_stock
    en_stock.boolean = True
    en_stock.short_description = 'En Stock'

    def balancines_instalados(self, obj):
        from django.db.models import Q
        count = BalancinIndividual.objects.filter(
            Q(torre__tipo_balancin_ascendente=obj.codigo) |
            Q(torre__tipo_balancin_descendente=obj.codigo)
        ).count()
        return count
    balancines_instalados.short_description = 'Instalados'


# ========== BALANCÍN INDIVIDUAL ==========
@admin.register(BalancinIndividual)
class BalancinIndividualAdmin(admin.ModelAdmin):
    list_display = (
        'codigo', 'torre_info', 'sentido',
        'rango_horas_cambio_oh',
        'tipo_balancin', 'fecha_registro',
        'ultima_oh'
    )
    list_filter = ('sentido', 'torre__linea', 'torre__seccion')
    search_fields = (
        'codigo', 'torre__numero_torre',
        'torre__linea__nombre', 'observaciones'
    )
    readonly_fields = ('fecha_registro',)
    raw_id_fields = ('torre',)

    def torre_info(self, obj):
        url = reverse('admin:balancines_torre_change', args=[obj.torre.id])
        return format_html(
            '<a href="{}">L{} - Torre {}</a><br><small>{}</small>',
            url,
            obj.torre.linea_id,
            obj.torre.numero_torre,
            obj.torre.seccion.nombre
        )
    torre_info.short_description = 'Torre'

    def tipo_balancin(self, obj):
        codigo = obj.tipo_balancin_codigo
        if codigo:
            url = reverse('admin:balancines_tipobalancin_change', args=[codigo])
            return format_html('<a href="{}">{}</a>', url, codigo)
        return '-'
    tipo_balancin.short_description = 'Tipo'

    def ultima_oh(self, obj):
        ultima = obj.ordenes_horas.order_by('-fecha_oh').first()
        if ultima:
            return format_html(
                '<span title="OH#{} - {} hrs">OH#{}</span><br><small>{}</small>',
                ultima.numero_oh,
                ultima.horas_operacion or 0,
                ultima.numero_oh,
                ultima.fecha_oh.strftime('%d/%m/%Y')
            )
        return format_html('<span style="color: gray;">Sin OH</span>')
    ultima_oh.short_description = 'Última OH'


# ========== REPUESTOS ==========
@admin.register(RepuestoBalancin)
class RepuestoBalancinAdmin(admin.ModelAdmin):
    list_display = ('item', 'descripcion_corta', 'cantidad',
                    'ubicacion', 'fecha_ingreso', 'en_stock')
    search_fields = ('item', 'descripcion', 'ubicacion')
    readonly_fields = (
        'fecha_ingreso',
        'fecha_ultimo_movimiento',
        'fecha_ultima_salida'
    )

    def descripcion_corta(self, obj):
        return obj.descripcion[:100] + '...' if len(obj.descripcion) > 100 else obj.descripcion
    descripcion_corta.short_description = 'Descripción'

    def en_stock(self, obj):
        return obj.en_stock
    en_stock.boolean = True


@admin.register(RepuestoAdicional)
class RepuestoAdicionalAdmin(admin.ModelAdmin):
    list_display = ('item', 'descripcion', 'cantidad',
                    'ubicacion', 'fecha_ingreso', 'en_stock')
    search_fields = ('item', 'descripcion', 'ubicacion')
    readonly_fields = (
        'fecha_ingreso',
        'fecha_ultimo_movimiento',
        'fecha_ultima_salida'
    )

    def en_stock(self, obj):
        return obj.en_stock
    en_stock.boolean = True


# ========== HISTORIALES ==========
@admin.register(HistorialRepuesto)
class HistorialRepuestoAdmin(admin.ModelAdmin):
    list_display = ('repuesto', 'tipo_movimiento',
                    'cantidad', 'stock_restante',
                    'fecha_movimiento')
    readonly_fields = ('fecha_movimiento',)


@admin.register(HistorialAdicional)
class HistorialAdicionalAdmin(admin.ModelAdmin):
    list_display = ('repuesto', 'tipo_movimiento',
                    'cantidad', 'stock_restante',
                    'usuario', 'fecha_movimiento')
    readonly_fields = ('fecha_movimiento',)


@admin.register(HistorialOH)
class HistorialOHAdmin(admin.ModelAdmin):
    list_display = (
        'linea_nombre', 'torre_numero', 'sentido',
        'tipo_balancin', 'numero_oh',
        'fecha_oh', 'horas_operacion',
        'backlog', 'estado_color'
    )
    ordering = ('-fecha_oh',)
    raw_id_fields = ('balancin',)
    readonly_fields = ('fecha_registro', 'backlog',
                       'dia_semana', 'anio')

    def estado_color(self, obj):
        if obj.backlog is None:
            return format_html('<span style="color: gray;">⚪ Sin OH</span>')
        elif obj.backlog < 0:
            return format_html('<span style="color: red; font-weight: bold;">🔴 Crítico</span>')
        elif obj.backlog < 5000:
            return format_html('<span style="color: orange; font-weight: bold;">🟡 Alerta</span>')
        else:
            return format_html('<span style="color: green; font-weight: bold;">🟢 Normal</span>')
    estado_color.short_description = 'Estado'


# ========== TIPO BALANCÍN - REPUESTO ==========