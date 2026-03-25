# ============================================================
# BALANCINES - MODELOS
# ============================================================

# ========== DJANGO CORE ==========
from django.db import models
from django.contrib.auth.models import AbstractBaseUser, BaseUserManager, PermissionsMixin
from django.utils import timezone
from django.utils.translation import gettext_lazy as _

# ========== PYTHON STANDARD LIBRARY ==========
from datetime import datetime, timedelta
import re


# ============================================================
# USUARIOS Y AUTENTICACIÓN
# ============================================================

class UsuarioManager(BaseUserManager):
    """Manager personalizado para el modelo Usuario"""
    
    def create_user(self, email, nombre, password=None, **extra_fields):
        if not email:
            raise ValueError('El usuario debe tener un email')
        email = self.normalize_email(email)
        user = self.model(email=email, nombre=nombre, **extra_fields)
        user.set_password(password)
        user.save(using=self._db)
        return user
    
    def create_superuser(self, email, nombre, password=None, **extra_fields):
        extra_fields.setdefault('is_staff', True)
        extra_fields.setdefault('is_superuser', True)
        extra_fields.setdefault('is_active', True)
        extra_fields.setdefault('rol', 'jefe')
        return self.create_user(email, nombre, password, **extra_fields)


class Usuario(AbstractBaseUser, PermissionsMixin):
    """Modelo personalizado de usuario"""
    
    class RolUsuario(models.TextChoices):
        JEFE = 'jefe', _('Jefe')
        SUPERVISOR = 'supervisor', _('Supervisor')
        TECNICO = 'tecnico', _('Técnico')
    
    email = models.EmailField(_('email'), max_length=255, unique=True, db_index=True)
    nombre = models.CharField(_('nombre completo'), max_length=150)
    rol = models.CharField(_('rol'), max_length=20, choices=RolUsuario.choices, default=RolUsuario.TECNICO)
    is_active = models.BooleanField(_('activo'), default=True)
    is_staff = models.BooleanField(_('staff'), default=False)
    fecha_registro = models.DateTimeField(_('fecha de registro'), default=timezone.now)
    ultima_actividad = models.DateTimeField(_('última actividad'), auto_now=True)
    
    objects = UsuarioManager()
    USERNAME_FIELD = 'email'
    REQUIRED_FIELDS = ['nombre']
    
    class Meta:
        db_table = 'app_usuario'
        verbose_name = _('usuario')
        verbose_name_plural = _('usuarios')
        ordering = ['-fecha_registro']
    
    def __str__(self):
        return f"{self.nombre} ({self.email})"
    
    def get_username(self):
        return self.email
    
    @property
    def username(self):
        return self.email
    
    @property
    def date_joined(self):
        return self.fecha_registro
    
    def get_full_name(self):
        return self.nombre
    
    def get_short_name(self):
        return self.nombre.split()[0] if self.nombre else self.email
    
    @property
    def es_jefe(self):
        return self.rol == 'jefe'
    
    @property
    def es_supervisor(self):
        return self.rol == 'supervisor'
    
    @property
    def es_tecnico(self):
        return self.rol == 'tecnico'


class RegistroActividad(models.Model):
    """Registro de actividades de usuarios"""
    
    usuario = models.ForeignKey(Usuario, on_delete=models.CASCADE, related_name='actividades')
    accion = models.CharField(max_length=255)
    fecha = models.DateTimeField(auto_now_add=True)
    detalles = models.TextField(blank=True)
    
    class Meta:
        db_table = 'app_registroactividad'
        verbose_name = 'registro de actividad'
        verbose_name_plural = 'registros de actividad'
        ordering = ['-fecha']
    
    def __str__(self):
        return f"{self.usuario.email} - {self.accion} - {self.fecha}"


# ============================================================
# CATÁLOGOS (Líneas, Secciones, Torres)
# ============================================================

class Linea(models.Model):
    """Líneas de producción"""
    
    id = models.AutoField(primary_key=True)
    nombre = models.CharField('Nombre', max_length=100)
    color = models.CharField('Color Bootstrap', max_length=30, default='secondary')
    descripcion = models.TextField('Descripción', blank=True, null=True)
    fecha_registro = models.DateTimeField('Fecha de registro', auto_now_add=True)
    
    class Meta:
        db_table = 'app_linea'
        verbose_name = 'Línea'
        verbose_name_plural = 'Líneas'
        ordering = ['nombre']
    
    def __str__(self):
        return self.nombre


class Seccion(models.Model):
    """Secciones de las líneas"""
    
    id = models.AutoField(primary_key=True)
    nombre = models.CharField('Nombre', max_length=50)
    
    class Meta:
        db_table = 'app_seccion'
        verbose_name = 'Sección'
        verbose_name_plural = 'Secciones'
        ordering = ['nombre']
    
    def __str__(self):
        return self.nombre


class Torre(models.Model):
    """Torres donde se instalan los balancines"""
    
    id = models.AutoField(primary_key=True)
    linea = models.ForeignKey(Linea, on_delete=models.CASCADE, related_name='torres', db_column='linea_id')
    seccion = models.ForeignKey(Seccion, on_delete=models.CASCADE, related_name='torres', db_column='seccion_id')
    numero_torre = models.CharField('Número de torre', max_length=10)
    tipo_balancin_ascendente = models.CharField('Tipo balancín ascendente', max_length=50, null=True, blank=True)
    tipo_balancin_descendente = models.CharField('Tipo balancín descendente', max_length=50, null=True, blank=True)
    observaciones = models.TextField('Observaciones', blank=True, null=True)
    fecha_registro = models.DateTimeField('Fecha de registro', auto_now_add=True)
    
    class Meta:
        db_table = 'app_torre'
        verbose_name = 'Torre'
        verbose_name_plural = 'Torres'
        ordering = ['linea', 'numero_torre']
        unique_together = ['linea', 'numero_torre', 'seccion']
    
    def __str__(self):
        return f"L{self.linea_id}-T{self.numero_torre} (Secc:{self.seccion.nombre})"


# ============================================================
# TIPOS / MODELOS DE BALANCINES
# ============================================================

class TipoBalancin(models.Model):
    """Modelos/tipos de balancines (catálogo)"""
    
    class Tipo(models.TextChoices):
        COMPRESION = 'compresion', 'Compresión'
        SOPORTE = 'soporte', 'Soporte'
        COMBINADOS = 'combinados', 'Combinados'
    
    codigo = models.CharField('Código', max_length=50, primary_key=True, help_text='Ej: 16N/4TR-420C')
    tipo = models.CharField('Tipo', max_length=20, choices=Tipo.choices, default=Tipo.SOPORTE)
    cantidad_total = models.PositiveIntegerField('Cantidad total', default=0)
    fecha_registro = models.DateTimeField('Fecha de registro', auto_now_add=True)
    fecha_actualizacion = models.DateTimeField('Última actualización', auto_now=True)
    
    class Meta:
        db_table = 'app_tipobalancin'
        verbose_name = 'Modelo de Balancín'
        verbose_name_plural = 'Modelos de Balancines'
        ordering = ['tipo', 'codigo']
    
    def __str__(self):
        return f"{self.codigo} ({self.get_tipo_display()})"
    
    @property
    def en_stock(self):
        return self.cantidad_total > 0
    
    @property
    def balancines_instalados(self):
        """Contar balancines de este tipo instalados en torres"""
        from .models import BalancinIndividual
        from django.db.models import Q
        return BalancinIndividual.objects.filter(
            Q(torre__tipo_balancin_ascendente=self.codigo) |
            Q(torre__tipo_balancin_descendente=self.codigo)
        ).count()


# ============================================================
# BALANCINES INDIVIDUALES INSTALADOS EN TORRES
# ============================================================

class BalancinIndividual(models.Model):
    """Balancines individuales instalados en torres"""
    
    class SentidoBalancin(models.TextChoices):
        ASCENDENTE = 'ASCENDENTE', 'Ascendente'
        DESCENDENTE = 'DESCENDENTE', 'Descendente'
    
    ESTADO_CHOICES = [
        ('OPERANDO', 'Operando'),
        ('MANTENIMIENTO', 'En Mantenimiento'),
        ('OH_PENDIENTE', 'OH Pendiente'),
    ]
    
    # Identificación
    codigo = models.CharField(
        'Código',
        max_length=50,
        primary_key=True,
        help_text='Ej: BAL-16N/4TR-0001'
    )
    
    # Relaciones
    torre = models.ForeignKey(
        Torre,
        on_delete=models.CASCADE,
        related_name='balancines',
        verbose_name='Torre',
        db_column='torre_id'
    )
    
    # Características
    sentido = models.CharField(
        'Sentido',
        max_length=20,
        choices=SentidoBalancin.choices,
        default=SentidoBalancin.ASCENDENTE
    )
    rango_horas_cambio_oh = models.PositiveIntegerField(
        'Rango de horas para cambio de OH',
        default=40000,
        help_text='Horas de operación antes de requerir mantenimiento'
    )
    
    # Estado
    estado = models.CharField(
        'Estado',
        max_length=20,
        choices=ESTADO_CHOICES,
        default='OPERANDO',
        db_index=True,
        help_text='Estado actual del balancín'
    )
    fecha_cambio_estado = models.DateTimeField(
        'Fecha cambio de estado',
        auto_now=True,
        help_text='Última vez que cambió el estado'
    )
    observaciones_estado = models.TextField(
        'Observaciones del estado',
        blank=True,
        null=True,
        help_text='Motivo del cambio de estado o notas adicionales'
    )
    
    # Metadatos
    observaciones = models.TextField('Observaciones', blank=True, null=True)
    fecha_registro = models.DateTimeField('Fecha de registro', auto_now_add=True)
    
    class Meta:
        db_table = 'app_balancinindividual'
        verbose_name = 'Balancín Individual'
        verbose_name_plural = 'Balancines Individuales'
        ordering = ['codigo']
        indexes = [
            models.Index(fields=['torre', 'sentido']),
        ]
    
    def __str__(self):
        return f"{self.codigo} - {self.torre}"
    
    @property
    def tipo_balancin_codigo(self):
        """Obtener el código del tipo de balancín desde la torre"""
        if self.sentido == 'ASCENDENTE':
            return self.torre.tipo_balancin_ascendente
        return self.torre.tipo_balancin_descendente
    
    @property
    def tipo_balancin(self):
        """Obtener el objeto TipoBalancin si existe"""
        codigo = self.tipo_balancin_codigo
        if codigo:
            try:
                return TipoBalancin.objects.get(codigo=codigo)
            except TipoBalancin.DoesNotExist:
                return None
        return None
    
    @property
    def tiene_oh_pendiente(self):
        """Verificar si necesita cambio de OH"""
        ultimo_oh = self.ordenes_horas.order_by('-fecha_oh').first()
        if ultimo_oh and ultimo_oh.horas_operacion:
            return ultimo_oh.horas_operacion >= self.rango_horas_cambio_oh
        return False


# ============================================================
# ÓRDENES DE HORAS (OH) DE BALANCINES
# ============================================================

class BalancinOH(models.Model):
    """Órdenes de horas de balancines"""
    
    balancin = models.ForeignKey(
        BalancinIndividual,
        on_delete=models.CASCADE,
        related_name='ordenes_horas',
        verbose_name='Balancín',
        db_column='balancin_codigo',
        to_field='codigo'
    )
    numero_oh = models.PositiveIntegerField('Número de OH')
    fecha_oh = models.DateField('Fecha de OH')
    horas_operacion = models.PositiveIntegerField('Horas de operación', null=True, blank=True)
    observaciones = models.TextField('Observaciones', blank=True, null=True)
    fecha_registro = models.DateTimeField('Fecha de registro', auto_now_add=True)
    
    class Meta:
        db_table = 'app_balancin_oh'
        verbose_name = 'Orden de Horas de Balancín'
        verbose_name_plural = 'Órdenes de Horas de Balancines'
        ordering = ['-fecha_oh']
        unique_together = ['balancin', 'numero_oh']
    
    def __str__(self):
        return f"{self.balancin.codigo} - OH#{self.numero_oh}"


# ============================================================
# HISTORIAL DE BALANCINES
# ============================================================

class HistorialBalancin(models.Model):
    """Historial de cambios en balancines"""
    
    balancin = models.ForeignKey(
        BalancinIndividual,
        on_delete=models.CASCADE,
        related_name='historial',
        verbose_name='Balancín',
        db_column='balancin_id'
    )
    estado_anterior = models.CharField('Estado anterior', max_length=20)
    estado_nuevo = models.CharField('Estado nuevo', max_length=20)
    accion = models.CharField('Acción', max_length=100)
    observaciones = models.TextField('Observaciones', blank=True)
    fecha_cambio = models.DateTimeField('Fecha de cambio', default=timezone.now)
    usuario = models.ForeignKey(
        Usuario,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        db_column='usuario_id'
    )
    
    class Meta:
        db_table = 'app_historialbalancin'
        verbose_name = 'Historial de Balancín'
        verbose_name_plural = 'Historial de Balancines'
        ordering = ['-fecha_cambio']
    
    def __str__(self):
        return f"{self.balancin.codigo} - {self.estado_anterior} → {self.estado_nuevo}"


# ============================================================
# INVENTARIO DE REPUESTOS
# ============================================================

class RepuestoBalancin(models.Model):
    """Repuestos para balancines"""
    
    item = models.CharField('Código', max_length=50, primary_key=True)
    descripcion = models.TextField('Descripción')
    cantidad = models.PositiveIntegerField('Cantidad', default=0)
    fecha_ingreso = models.DateTimeField('Fecha de ingreso', default=timezone.now)
    fecha_ultimo_movimiento = models.DateTimeField('Último movimiento', auto_now=True)
    fecha_ultima_salida = models.DateTimeField('Última salida', null=True, blank=True)
    ubicacion = models.CharField('Ubicación', max_length=100, blank=True)
    observaciones = models.TextField('Observaciones', blank=True)
    
    class Meta:
        db_table = 'app_repuestobalancin'
        verbose_name = 'Repuesto para Balancín'
        verbose_name_plural = 'Repuestos para Balancines'
        ordering = ['item']
    
    def __str__(self):
        return f"{self.item} - Stock: {self.cantidad}"
    
    @property
    def en_stock(self):
        return self.cantidad > 0


class RepuestoAdicional(models.Model):
    """Repuestos adicionales"""
    
    item = models.CharField('Código', max_length=50, primary_key=True)
    descripcion = models.TextField('Descripción')
    cantidad = models.PositiveIntegerField('Cantidad', default=0)
    fecha_ingreso = models.DateTimeField('Fecha de ingreso', default=timezone.now)
    fecha_ultimo_movimiento = models.DateTimeField('Último movimiento', auto_now=True)
    fecha_ultima_salida = models.DateTimeField('Última salida', null=True, blank=True)
    ubicacion = models.CharField('Ubicación', max_length=100, blank=True)
    observaciones = models.TextField('Observaciones', blank=True)
    
    class Meta:
        db_table = 'app_repuestoadicional'
        verbose_name = 'Repuesto Adicional'
        verbose_name_plural = 'Repuestos Adicionales'
        ordering = ['item']
    
    def __str__(self):
        return f"{self.item} - Stock: {self.cantidad}"
    
    @property
    def en_stock(self):
        return self.cantidad > 0


class HistorialRepuesto(models.Model):
    """Historial de movimientos de repuestos de balancín"""
    
    TIPO_MOVIMIENTO = [
        ('entrada', 'Entrada'),
        ('salida', 'Salida'),
    ]
    
    repuesto = models.ForeignKey(
        RepuestoBalancin,
        on_delete=models.CASCADE,
        related_name='historial',
        db_column='repuesto_id'
    )
    tipo_movimiento = models.CharField('Tipo', max_length=20, choices=TIPO_MOVIMIENTO)
    cantidad = models.IntegerField('Cantidad')
    stock_restante = models.PositiveIntegerField('Stock restante')
    observaciones = models.TextField('Observaciones', blank=True)
    fecha_movimiento = models.DateTimeField('Fecha', default=timezone.now)
    
    class Meta:
        db_table = 'app_historialrepuesto'
        verbose_name = 'Historial de Repuesto'
        verbose_name_plural = 'Historial de Repuestos'
        ordering = ['-fecha_movimiento']
    
    def __str__(self):
        return f"{self.repuesto.item} - {self.tipo_movimiento} ({self.cantidad})"


class HistorialAdicional(models.Model):
    """Historial para repuestos adicionales"""
    
    TIPO_MOVIMIENTO = [
        ('entrada', 'Entrada'),
        ('salida', 'Salida'),
        ('creacion', 'Creación'),
        ('actualizacion', 'Actualización'),
    ]
    
    repuesto = models.ForeignKey(
        RepuestoAdicional,
        on_delete=models.CASCADE,
        related_name='historial',
        db_column='repuesto_id'
    )
    tipo_movimiento = models.CharField('Tipo', max_length=20, choices=TIPO_MOVIMIENTO)
    cantidad = models.IntegerField('Cantidad')
    stock_restante = models.PositiveIntegerField('Stock restante')
    observaciones = models.TextField('Observaciones', blank=True)
    usuario = models.ForeignKey(
        Usuario,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        db_column='usuario_id'
    )
    fecha_movimiento = models.DateTimeField('Fecha', default=timezone.now)
    
    class Meta:
        db_table = 'app_historialadicional'
        verbose_name = 'Historial de Repuesto Adicional'
        verbose_name_plural = 'Historial de Repuestos Adicionales'
        ordering = ['-fecha_movimiento']
    
    def __str__(self):
        return f"{self.repuesto.item} - {self.tipo_movimiento} ({self.cantidad})"


# ============================================================
# ACTIVITY LOG
# ============================================================

class ActivityLog(models.Model):
    """Registro de todas las actividades del sistema"""
    
    ACTION_CHOICES = [
        ('CREATE', 'Creación'),
        ('UPDATE', 'Actualización'),
        ('DELETE', 'Eliminación'),
        ('CHECKOUT', 'Retiro/Salida'),
        ('CHECKIN', 'Ingreso/Entrada'),
        ('STATUS_CHANGE', 'Cambio de Estado'),
        ('VIEW', 'Consulta'),
        ('LOGIN', 'Inicio de Sesión'),
        ('LOGOUT', 'Cierre de Sesión'),
        ('BACKUP', 'Respaldo'),
        ('EXPORT', 'Exportación'),
    ]
    
    MODULE_CHOICES = [
        ('BALANCIN_INDIVIDUAL', 'Balancín Individual'),
        ('TIPO_BALANCIN', 'Tipo de Balancín'),
        ('REPUESTO_BALANCIN', 'Repuesto de Balancín'),
        ('REPUESTO_ADICIONAL', 'Repuesto Adicional'),
        ('TORRE', 'Torre'),
        ('LINEA', 'Línea'),
        ('USER', 'Usuario'),
        ('SYSTEM', 'Sistema'),
        ('INVENTORY', 'Inventario General'),
    ]
    
    user = models.ForeignKey(
        Usuario,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        verbose_name="Usuario",
        db_column='user_id'
    )
    action = models.CharField(max_length=50, choices=ACTION_CHOICES, verbose_name="Acción")
    module = models.CharField(max_length=50, choices=MODULE_CHOICES, verbose_name="Módulo")
    description = models.TextField(verbose_name="Descripción detallada")
    object_id = models.CharField(max_length=100, null=True, blank=True, verbose_name="ID del Objeto")
    object_name = models.CharField(max_length=200, null=True, blank=True, verbose_name="Nombre del Objeto")
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    user_agent = models.TextField(null=True, blank=True)
    browser_info = models.CharField(max_length=255, null=True, blank=True)
    created_at = models.DateTimeField(default=timezone.now, verbose_name="Fecha y hora")
    old_values = models.JSONField(null=True, blank=True)
    new_values = models.JSONField(null=True, blank=True)
    
    class Meta:
        db_table = 'app_activitylog'
        verbose_name = "Registro de Actividad"
        verbose_name_plural = "Registros de Actividades"
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['-created_at']),
            models.Index(fields=['user']),
            models.Index(fields=['action']),
            models.Index(fields=['module']),
            models.Index(fields=['object_id']),
        ]
    
    def __str__(self):
        return f"{self.get_action_display()} - {self.get_module_display()} - {self.created_at.strftime('%Y-%m-%d %H:%M')}"


# ============================================================
# HISTORIAL COMPLETO DE OH
# ============================================================

class HistorialOH(models.Model):
    """Historial completo de Órdenes de Horas (OH) - Versión desnormalizada"""
    
    # Identificación
    balancin = models.ForeignKey(
        BalancinIndividual,
        on_delete=models.CASCADE,
        related_name='historial_oh_completo',
        db_column='balancin_codigo',
        to_field='codigo'
    )
    
    # Datos fijos (desnormalizados para consultas rápidas)
    linea_nombre = models.CharField('Línea', max_length=50)
    torre_numero = models.CharField('Torre', max_length=10)
    sentido = models.CharField('Sentido', max_length=20)
    tipo_balancin = models.CharField('Tipo', max_length=50)
    rango_oh_horas = models.IntegerField('Rango OH (horas)')
    
    # Datos de configuración
    inicio_oc = models.DateField('Inicio OC')
    horas_promedio_dia = models.IntegerField('Horas promedio/día')
    factor_correccion = models.DecimalField('Factor', max_digits=3, decimal_places=2, default=1.00)
    
    # Datos del OH
    numero_oh = models.IntegerField('N° OH')
    fecha_oh = models.DateField('Fecha OH')
    horas_operacion = models.IntegerField('Horas operación', null=True, blank=True)
    backlog = models.IntegerField('Backlog', null=True, blank=True)
    anio = models.IntegerField('Año', null=True, blank=True)
    dia_semana = models.CharField('Día semana', max_length=20, blank=True)
    
    # Metadatos
    observaciones = models.TextField('Observaciones', blank=True)
    fecha_registro = models.DateTimeField('Fecha registro', auto_now_add=True)
    usuario_registro = models.CharField('Usuario', max_length=100, blank=True)
    
    class Meta:
        db_table = 'app_historial_oh'
        verbose_name = 'Historial OH'
        verbose_name_plural = 'Historiales OH'
        unique_together = ['balancin', 'numero_oh']
        indexes = [
            models.Index(fields=['linea_nombre', 'torre_numero']),
            models.Index(fields=['fecha_oh']),
            models.Index(fields=['anio']),
            models.Index(fields=['backlog']),
        ]
        ordering = ['linea_nombre', 'torre_numero', 'sentido', 'numero_oh']
    
    def save(self, *args, **kwargs):
        # Calcular día de la semana automáticamente
        if self.fecha_oh and not self.dia_semana:
            dias = ['Sunday', 'Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday']
            self.dia_semana = dias[self.fecha_oh.weekday()]
        
        # Calcular año
        if self.fecha_oh and not self.anio:
            self.anio = self.fecha_oh.year
        
        # Recalcular backlog cuando hay horas y rango
        if self.horas_operacion is not None and self.rango_oh_horas:
            self.backlog = self.rango_oh_horas - self.horas_operacion
        
        super().save(*args, **kwargs)
    
    def __str__(self):
        return f"{self.linea_nombre} T{self.torre_numero} {self.sentido} - OH#{self.numero_oh}"


# ============================================================
# CONFIGURACIÓN DE REPUESTOS POR TIPO
# ============================================================

class ConfiguracionRepuestosPorTipo(models.Model):
    """Configuración de qué repuestos necesita cada tipo de balancín"""
    
    GRUPO_CHOICES = [
        ('POLEAS', 'Poleas'),
        ('SEGMENTOS_2P', 'Segmentos 2P'),
        ('SEGMENTOS_4P', 'Segmentos 4P'),
        ('CONJUNTOS', 'Conjuntos'),
        ('OTROS', 'Otros'),
    ]
    
    tipo_balancin = models.ForeignKey(
        'TipoBalancin',
        on_delete=models.CASCADE,
        related_name='config_repuestos',
        verbose_name='Tipo de balancín',
        db_column='tipo_balancin_codigo',
        to_field='codigo'
    )
    repuesto = models.ForeignKey(
        'RepuestoBalancin',
        on_delete=models.PROTECT,
        related_name='configurado_en_tipos',
        verbose_name='Repuesto',
        null=True,
        blank=True
    )
    
    # Datos del Excel
    id_original = models.CharField('ID Excel', max_length=20, help_text='Ej: 10870308')
    descripcion = models.TextField('Descripción')
    cantidad_por_balancin = models.PositiveIntegerField('Cantidad por balancín', default=1)
    cantidad_total = models.PositiveIntegerField('Cantidad total', default=0)
    
    # Jerarquía
    es_conjunto = models.BooleanField('Es un conjunto', default=False)
    conjunto_padre = models.ForeignKey(
        'self',
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='componentes',
        verbose_name='Conjunto padre'
    )
    
    # Agrupación visual
    grupo = models.CharField('Grupo', max_length=20, choices=GRUPO_CHOICES, default='OTROS')
    orden = models.PositiveIntegerField('Orden', default=0)
    
    class Meta:
        db_table = 'app_config_repuestos_tipo'
        verbose_name = 'Configuración de repuestos por tipo'
        verbose_name_plural = 'Configuraciones de repuestos por tipo'
        ordering = ['tipo_balancin', 'grupo', 'orden']
        unique_together = ['tipo_balancin', 'repuesto']
    
    def __str__(self):
        return f"{self.tipo_balancin.codigo} - {self.id_original}"


# ============================================================
# FORMULARIOS DE REACONDICIONAMIENTO
# ============================================================

class FormularioReacondicionamiento(models.Model):
    """Cabecera del formulario de control de reacondicionamiento"""
    
    TIPO_CHOICES = [
        ('4T-501C', '4T-501C'),
        ('6T-501C', '6T-501C'),
        ('8T-501C', '8T-501C'),
        ('10T-501C', '10T-501C'),
        ('12T-501C', '12T-501C'),
        ('8N/4TR-420C', '8N/4TR-420C'),
        ('10N/4TR-420C', '10N/4TR-420C'),
        ('12N/4TR-420C', '12N/4TR-420C'),
        ('14N/4TR-420C', '14N/4TR-420C'),
        ('16N/4TR-420C', '16N/4TR-420C'),
        ('4T/4N-420C', '4T/4N-420C'),
    ]
    
    # Identificación
    codigo_formulario = models.CharField(
        'Código formulario',
        max_length=50,
        primary_key=True,
        help_text='Ej: TRM-FCRB-16N-4TR-420C-001'
    )
    tipo = models.CharField('Tipo', max_length=20, choices=TIPO_CHOICES)
    
    # Relaciones
    balancin = models.ForeignKey(
        'BalancinIndividual',
        on_delete=models.PROTECT,
        related_name='formularios_reacondicionamiento',
        verbose_name='Balancín'
    )
    historial_oh = models.ForeignKey(
        'HistorialOH',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='formularios'
    )
    
    # Fechas y horas
    fecha = models.DateField('Fecha', default=timezone.now)
    horas_funcionamiento = models.PositiveIntegerField('Horas de funcionamiento')
    
    # Posiciones
    linea_inicial = models.CharField('Línea inicial', max_length=50, blank=True)
    torre_inicial = models.CharField('Torre inicial', max_length=50, blank=True)
    linea_final = models.CharField('Línea final', max_length=50, blank=True)
    torre_final = models.CharField('Torre final', max_length=50, blank=True)
    sentido_final = models.CharField(
        'Sentido final',
        max_length=20,
        choices=BalancinIndividual.SentidoBalancin.choices,
        null=True,
        blank=True,
        help_text='ASCENDENTE o DESCENDENTE según la torre de destino'
    )
    
    # Análisis predictivo
    control_particulas = models.BooleanField('Control de partículas magnéticas', default=False)
    codigo_informe = models.CharField('Código de informe', max_length=50, blank=True)
    
    # Verificaciones
    torque_verificado = models.BooleanField('Torque verificado', default=False)
    limpieza_verificada = models.BooleanField('Limpieza de uniones', default=False)
    continuidad_verificada = models.BooleanField('Continuidad verificada', default=False)
    
    # Responsables
    realizado_por_analisis = models.ForeignKey(
        Usuario,
        on_delete=models.PROTECT,
        related_name='formularios_analisis',
        verbose_name='Realizado por (análisis)',
        null=True,
        blank=True
    )
    realizado_por_recambio = models.ForeignKey(
        Usuario,
        on_delete=models.PROTECT,
        related_name='formularios_recambio',
        verbose_name='Realizado por (recambio)',
        null=True,
        blank=True
    )
    aprobado_por = models.ForeignKey(
        Usuario,
        on_delete=models.PROTECT,
        related_name='formularios_aprobados',
        verbose_name='Aprobado por',
        null=True,
        blank=True
    )
    
    # Metadatos
    fecha_creacion = models.DateTimeField('Fecha de creación', auto_now_add=True)
    fecha_actualizacion = models.DateTimeField('Última actualización', auto_now=True)
    usuario_creacion = models.ForeignKey(
        Usuario,
        on_delete=models.SET_NULL,
        null=True,
        related_name='formularios_creados'
    )
    
    class Meta:
        db_table = 'app_formulario_reacondicionamiento'
        verbose_name = 'Formulario de Reacondicionamiento'
        verbose_name_plural = 'Formularios de Reacondicionamiento'
        ordering = ['-fecha', '-fecha_creacion']
    
    def __str__(self):
        return self.codigo_formulario


class ItemFormularioReacondicionamiento(models.Model):
    """Detalle de los repuestos usados en un formulario"""
    
    formulario = models.ForeignKey(
        FormularioReacondicionamiento,
        on_delete=models.CASCADE,
        related_name='items'
    )
    configuracion = models.ForeignKey(
        'ConfiguracionRepuestosPorTipo',
        on_delete=models.PROTECT,
        verbose_name='Configuración original'
    )
    repuesto = models.ForeignKey(
        'RepuestoBalancin',
        on_delete=models.PROTECT,
        verbose_name='Repuesto'
    )
    
    # Datos del momento
    id_original = models.CharField('ID Excel', max_length=20)
    descripcion = models.TextField('Descripción')
    cantidad_requerida = models.PositiveIntegerField('Cantidad requerida')
    cantidad_usada = models.PositiveIntegerField('Cantidad usada', default=0)
    fue_reemplazado = models.BooleanField('¿Fue reemplazado?', default=False)
    observaciones = models.TextField('Observaciones', blank=True)
    
    # Control de stock
    stock_antes = models.PositiveIntegerField('Stock antes', null=True, blank=True)
    stock_despues = models.PositiveIntegerField('Stock después', null=True, blank=True)
    
    class Meta:
        db_table = 'app_item_formulario_reacondicionamiento'
        verbose_name = 'Item de Formulario'
        verbose_name_plural = 'Items de Formulario'
    
    def __str__(self):
        return f"{self.formulario.codigo_formulario} - {self.repuesto.item}"


class TecnicoFormulario(models.Model):
    """Técnicos que participaron en el reacondicionamiento"""
    
    formulario = models.ForeignKey(
        'FormularioReacondicionamiento',
        on_delete=models.CASCADE,
        related_name='tecnicos'
    )
    usuario = models.ForeignKey(
        'Usuario',
        on_delete=models.PROTECT,
        verbose_name='Técnico'
    )
    firma = models.CharField('Firma', max_length=100, blank=True)
    fecha_registro = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        db_table = 'app_tecnico_formulario'
        verbose_name = 'Técnico por Formulario'
        verbose_name_plural = 'Técnicos por Formulario'
        ordering = ['fecha_registro']
    
    def __str__(self):
        return f"{self.formulario.codigo_formulario} - {self.usuario.nombre}"


# ============================================================
# ALERTAS DE OVERHAUL
# ============================================================

class AlertaOH(models.Model):
    """Alertas automáticas generadas cuando un balancín necesita mantenimiento"""
    
    NIVEL_CHOICES = [
        ('VERDE', 'Normal'),
        ('ALERTA', 'Alerta'),
        ('VENCIDO', 'Vencido'),
    ]
    
    # Relación con el balancín
    balancin = models.ForeignKey(
        'BalancinIndividual',
        on_delete=models.CASCADE,
        related_name='alertas_oh',
        verbose_name='Balancín',
        db_column='balancin_codigo',
        to_field='codigo'
    )
    
    # Datos de la alerta
    nivel = models.CharField(
        'Nivel de alerta',
        max_length=20,
        choices=NIVEL_CHOICES,
        db_index=True
    )
    backlog_momento = models.IntegerField(
        'Backlog al momento de la alerta',
        help_text='Horas restantes (positivo) o excedidas (negativo)'
    )
    horas_operacion_momento = models.PositiveIntegerField(
        'Horas de operación al momento',
        help_text='Horas registradas cuando se generó la alerta'
    )
    
    # Fechas
    fecha_generacion = models.DateTimeField(
        'Fecha de generación',
        auto_now_add=True,
        db_index=True
    )
    fecha_estimada_vencimiento = models.DateField(
        'Fecha estimada de vencimiento',
        null=True,
        blank=True,
        help_text='Fecha estimada para backlog = 0'
    )
    
    # Estado de la alerta
    leida = models.BooleanField('Leída', default=False, db_index=True)
    fecha_lectura = models.DateTimeField('Fecha de lectura', null=True, blank=True)
    resuelta = models.BooleanField('Resuelta', default=False, db_index=True)
    fecha_resolucion = models.DateTimeField('Fecha de resolución', null=True, blank=True)
    
    # Relación con el mantenimiento que la resolvió
    formulario_resolucion = models.ForeignKey(
        'FormularioReacondicionamiento',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='alertas_resueltas',
        verbose_name='Formulario que resolvió la alerta'
    )
    
    # Usuarios relacionados
    usuario_lectura = models.ForeignKey(
        'Usuario',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='alertas_leidas',
        verbose_name='Usuario que leyó la alerta'
    )
    
    # Metadatos
    observaciones = models.TextField(
        'Observaciones',
        blank=True,
        help_text='Notas adicionales sobre la alerta'
    )
    
    class Meta:
        db_table = 'app_alerta_oh'
        verbose_name = 'Alerta de OverHaul'
        verbose_name_plural = 'Alertas de OverHaul'
        ordering = ['-fecha_generacion']
        indexes = [
            models.Index(fields=['nivel', 'leida', 'resuelta']),
            models.Index(fields=['balancin', '-fecha_generacion']),
            models.Index(fields=['fecha_estimada_vencimiento']),
        ]
    
    def __str__(self):
        return f"{self.balancin.codigo} - {self.get_nivel_display()} - {self.fecha_generacion.strftime('%d/%m/%Y')}"
    
    @property
    def color_bootstrap(self):
        """Color para la interfaz según el nivel"""
        colores = {
            'ALERTA': 'warning',
            'VENCIDO': 'orange',
            'VERDE': 'success',
        }
        return colores.get(self.nivel, 'secondary')
    
    @property
    def es_critica(self):
        """Indica si la alerta es crítica"""
        return self.nivel in ['VENCIDO']
    
    def marcar_como_leida(self, usuario=None):
        """Marca la alerta como leída"""
        self.leida = True
        self.fecha_lectura = timezone.now()
        if usuario:
            self.usuario_lectura = usuario
        self.save(update_fields=['leida', 'fecha_lectura', 'usuario_lectura'])
    
    def marcar_como_resuelta(self, formulario=None):
        """Marca la alerta como resuelta"""
        self.resuelta = True
        self.fecha_resolucion = timezone.now()
        if formulario:
            self.formulario_resolucion = formulario
        self.save(update_fields=['resuelta', 'fecha_resolucion', 'formulario_resolucion'])


# ============================================================
# REGISTRO DE TRABAJOS DEL TALLER
# ============================================================

class RegistroTallerDiario(models.Model):
    """Registro diario de actividades del taller"""
    
    AREA_CHOICES = [
        ('mecanica', 'Mecánica'),
        ('electromecanica', 'Electromecánica'),
        ('electronica', 'Electrónica'),
        ('soldadura', 'Soldadura'),
        ('inspeccion', 'Inspección'),
        ('general', 'General'),
    ]
    
    TURNO_CHOICES = [
        ('T1', 'T1'),
        ('T2', 'T2'),
        ('T3', 'T3'),
        ('T4', 'T4'),
        ('T5', 'T5'),
        ('T6', 'T6'),
    ]
    
    # Datos del registro
    fecha = models.DateField('Fecha', blank=True, null=True, help_text='Fecha del trabajo (se asigna automáticamente)')
    turno = models.CharField('Turno', max_length=20, choices=TURNO_CHOICES, blank=True, null=True)
    area = models.CharField('Área', max_length=20, choices=AREA_CHOICES)
    
    # Descripción del trabajo
    descripcion = models.TextField('¿Qué se hizo?')
    observaciones = models.TextField('Observaciones', blank=True)
    
    # Tipo de balancín
    tipo_balancin = models.ForeignKey(
        'TipoBalancin',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='registros_taller',
        verbose_name='Tipo de balancín trabajado'
    )
    cantidad_balancines = models.PositiveIntegerField(
        'Cantidad de balancines',
        default=0,
        help_text='Número de balancines trabajados'
    )
    
    # Técnico (el que inició sesión)
    tecnico = models.ForeignKey(
        'Usuario',
        on_delete=models.SET_NULL,
        null=True,
        related_name='trabajos_registrados',
        verbose_name='Técnico que realizó el trabajo',
        limit_choices_to={'rol__in': ['tecnico', 'supervisor']}
    )
    
    # Insumos
    repuestos_balancin_usados = models.ManyToManyField(
        'RepuestoBalancin',
        through='RegistroRepuestoBalancin',
        blank=True,
        verbose_name='Repuestos de balancín usados'
    )
    repuestos_adicionales_usados = models.ManyToManyField(
        'RepuestoAdicional',
        through='RegistroRepuestoAdicional',
        blank=True,
        verbose_name='Repuestos adicionales usados'
    )
    consumibles = models.TextField(
        'Consumibles utilizados',
        blank=True,
        help_text='Ej: Soldadura E7018 (2kg), Aceite hidráulico (5L), Grasa (1kg)'
    )
    
    # Metadatos
    registrado_por = models.ForeignKey(
        'Usuario',
        on_delete=models.SET_NULL,
        null=True,
        related_name='registros_creados',
        verbose_name='Registrado por'
    )
    fecha_registro = models.DateTimeField('Fecha de registro', auto_now_add=True)
    actualizado_en = models.DateTimeField('Última actualización', auto_now=True)
    
    class Meta:
        db_table = 'app_registro_taller_diario'
        verbose_name = 'Registro de Taller'
        verbose_name_plural = 'Registros del Taller'
        ordering = ['-fecha', '-fecha_registro']
    
    def __str__(self):
        return f"{self.fecha} - {self.get_area_display()}: {self.descripcion[:50]}"


class RegistroRepuestoBalancin(models.Model):
    """Repuestos de balancín usados en un registro"""
    
    registro = models.ForeignKey(RegistroTallerDiario, on_delete=models.CASCADE)
    repuesto = models.ForeignKey('RepuestoBalancin', on_delete=models.PROTECT)
    cantidad = models.DecimalField('Cantidad', max_digits=10, decimal_places=2)
    stock_antes = models.PositiveIntegerField('Stock antes', null=True, blank=True)
    stock_despues = models.PositiveIntegerField('Stock después', null=True, blank=True)
    
    class Meta:
        db_table = 'app_registro_repuesto_balancin'
    
    def save(self, *args, **kwargs):
        from django.utils import timezone
        
        # Asegurar que cantidad es un número
        if isinstance(self.cantidad, str):
            try:
                self.cantidad = float(self.cantidad)
            except ValueError:
                self.cantidad = 0
        
        if not self.stock_antes:
            self.stock_antes = self.repuesto.cantidad
        
        # Calcular nuevo stock
        nuevo_stock = int(self.stock_antes) - int(self.cantidad)
        self.stock_despues = max(0, nuevo_stock)
        
        # Actualizar el stock del repuesto
        self.repuesto.cantidad = self.stock_despues
        self.repuesto.fecha_ultimo_movimiento = timezone.now()
        self.repuesto.fecha_ultima_salida = timezone.now()
        self.repuesto.save()
        
        # Registrar en historial
        try:
            from .models import HistorialRepuesto
            HistorialRepuesto.objects.create(
                repuesto=self.repuesto,
                tipo_movimiento='salida',
                cantidad=-self.cantidad,
                stock_restante=self.stock_despues,
                observaciones=f"Uso en taller - {self.registro.descripcion[:100]}"
            )
        except Exception as e:
            print(f"Error al guardar historial: {e}")
        
        super().save(*args, **kwargs)


class RegistroRepuestoAdicional(models.Model):
    """Repuestos adicionales usados en un registro"""
    
    registro = models.ForeignKey(RegistroTallerDiario, on_delete=models.CASCADE)
    repuesto = models.ForeignKey('RepuestoAdicional', on_delete=models.PROTECT)
    cantidad = models.DecimalField('Cantidad', max_digits=10, decimal_places=2)
    stock_antes = models.PositiveIntegerField('Stock antes', null=True, blank=True)
    stock_despues = models.PositiveIntegerField('Stock después', null=True, blank=True)
    
    class Meta:
        db_table = 'app_registro_repuesto_adicional'
    
    def save(self, *args, **kwargs):
        from django.utils import timezone
        
        # Asegurar que cantidad es un número
        if isinstance(self.cantidad, str):
            try:
                self.cantidad = float(self.cantidad)
            except ValueError:
                self.cantidad = 0
        
        if not self.stock_antes:
            self.stock_antes = self.repuesto.cantidad
        
        # Calcular nuevo stock
        nuevo_stock = int(self.stock_antes) - int(self.cantidad)
        self.stock_despues = max(0, nuevo_stock)
        
        # Actualizar el stock del repuesto
        self.repuesto.cantidad = self.stock_despues
        self.repuesto.fecha_ultimo_movimiento = timezone.now()
        self.repuesto.fecha_ultima_salida = timezone.now()
        self.repuesto.save()
        
        # Registrar en historial
        try:
            from .models import HistorialAdicional
            HistorialAdicional.objects.create(
                repuesto=self.repuesto,
                tipo_movimiento='salida',
                cantidad=-self.cantidad,
                stock_restante=self.stock_despues,
                observaciones=f"Uso en taller - {self.registro.descripcion[:100]}"
            )
        except Exception as e:
            print(f"Error al guardar historial: {e}")
        
        super().save(*args, **kwargs)