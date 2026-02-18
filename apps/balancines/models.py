from django.db import models
from django.contrib.auth.models import AbstractBaseUser, BaseUserManager, PermissionsMixin
from django.utils import timezone
from django.utils.translation import gettext_lazy as _

# ========== USUARIOS ==========
class UsuarioManager(BaseUserManager):
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
    
    def get_username(self):
        return self.email
    
    @property
    def username(self):
        return self.email
    
    @property
    def date_joined(self):
        return self.fecha_registro
    
    class Meta:
        db_table = 'app_usuario'
        verbose_name = _('usuario')
        verbose_name_plural = _('usuarios')
        ordering = ['-fecha_registro']
    
    def __str__(self):
        return f"{self.nombre} ({self.email})"
    
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


# ========== CATÁLOGOS (Líneas, Secciones, Torres) ==========
class Linea(models.Model):
    """Líneas de producción"""
    id = models.AutoField(primary_key=True)
    nombre = models.CharField('Nombre', max_length=100)
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


# ========== TIPOS / MODELOS DE BALANCINES ==========
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


# ========== BALANCINES INDIVIDUALES INSTALADOS EN TORRES ==========
class BalancinIndividual(models.Model):
    """Balancines físicos instalados en torres"""
    
    class SentidoBalancin(models.TextChoices):
        ASCENDENTE = 'ASCENDENTE', 'Ascendente'
        DESCENDENTE = 'DESCENDENTE', 'Descendente'
    
    codigo = models.CharField(
        'Código',
        max_length=50,
        primary_key=True,
        help_text='Ej: BAL-16N/4TR-0001'
    )
    torre = models.ForeignKey(
        Torre,
        on_delete=models.CASCADE,
        related_name='balancines',
        verbose_name='Torre',
        db_column='torre_id'
    )
    sentido = models.CharField(
        'Sentido',
        max_length=20,
        choices=SentidoBalancin.choices,
        default=SentidoBalancin.ASCENDENTE
    )
    rango_horas_cambio_oh = models.PositiveIntegerField(
        'Rango de horas para cambio de OH',
        default=30000,
        help_text='Horas de operación antes de requerir mantenimiento'
    )
    observaciones = models.TextField(
        'Observaciones',
        blank=True,
        null=True
    )
    fecha_registro = models.DateTimeField(
        'Fecha de registro',
        auto_now_add=True
    )
    
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
        else:
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


# ========== ÓRDENES DE HORAS (OH) DE BALANCINES ==========
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


# ========== HISTORIAL DE BALANCINES ==========
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


# ========== INVENTARIO DE REPUESTOS ==========
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
    """Historial de movimientos de repuestos"""
    
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


# ========== ACTIVITY LOG ==========
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


# ========== NUEVO: HISTORIAL COMPLETO DE OH ==========
class HistorialOH(models.Model):
    """Historial completo de Órdenes de Horas (OH) - Versión desnormalizada"""
    
    # ===== IDENTIFICACIÓN =====
    balancin = models.ForeignKey(
        BalancinIndividual,
        on_delete=models.CASCADE,
        related_name='historial_oh_completo',
        db_column='balancin_codigo',
        to_field='codigo'
    )
    
    # ===== DATOS FIJOS (desnormalizados para consultas rápidas) =====
    linea_nombre = models.CharField('Línea', max_length=50)
    torre_numero = models.CharField('Torre', max_length=10)
    sentido = models.CharField('Sentido', max_length=20)
    tipo_balancin = models.CharField('Tipo', max_length=50)
    rango_oh_horas = models.IntegerField('Rango OH (horas)')
    
    # ===== DATOS DE CONFIGURACIÓN =====
    inicio_oc = models.DateField('Inicio OC')
    horas_promedio_dia = models.IntegerField('Horas promedio/día')
    factor_correccion = models.DecimalField('Factor', max_digits=3, decimal_places=2, default=1.00)
    
    # ===== DATOS DEL OH =====
    numero_oh = models.IntegerField('N° OH')
    fecha_oh = models.DateField('Fecha OH')
    horas_operacion = models.IntegerField('Horas operación', null=True, blank=True)
    backlog = models.IntegerField('Backlog', null=True, blank=True)
    anio = models.IntegerField('Año', null=True, blank=True)
    dia_semana = models.CharField('Día semana', max_length=20, blank=True)
    
    # ===== METADATOS =====
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
        
        # Calcular backlog si no está definido
        if self.horas_operacion and self.rango_oh_horas and self.backlog is None:
            self.backlog = self.rango_oh_horas - self.horas_operacion
        
        super().save(*args, **kwargs)
    
    def __str__(self):
        return f"{self.linea_nombre} T{self.torre_numero} {self.sentido} - OH#{self.numero_oh}"