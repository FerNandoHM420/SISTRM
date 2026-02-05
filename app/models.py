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
        verbose_name = 'registro de actividad'
        verbose_name_plural = 'registros de actividad'
        ordering = ['-fecha']
    
    def __str__(self):
        return f"{self.usuario.email} - {self.accion} - {self.fecha}"

# ========== INVENTARIO SIMPLIFICADO ==========
class TipoBalancin(models.Model):
    class Tipo(models.TextChoices):
        COMPRESION = 'compresion', 'Compresión'
        SOPORTE = 'soporte', 'Soporte'
        COMBINADOS = 'combinados', 'Combinados'
    
    codigo = models.CharField('Código', max_length=50, unique=True, primary_key=True, help_text='Ej: 4T-501C')
    tipo = models.CharField('Tipo', max_length=20, choices=Tipo.choices, default=Tipo.SOPORTE)
    cantidad_total = models.PositiveIntegerField('Cantidad total', default=0)
    fecha_registro = models.DateTimeField('Fecha de registro', auto_now_add=True)
    fecha_actualizacion = models.DateTimeField('Última actualización', auto_now=True)
    
    class Meta:
        verbose_name = 'Modelo de Balancín'
        verbose_name_plural = 'Modelos de Balancines'
        ordering = ['tipo', 'codigo']
    
    def __str__(self):
        return f"{self.codigo} ({self.get_tipo_display()}) - Cantidad: {self.cantidad_total}"
    
    @property
    def en_stock(self):
        return self.cantidad_total > 0

class BalancinIndividual(models.Model):
    serial = models.CharField('Serial', max_length=50, unique=True, primary_key=True, help_text='Ej: BAL-001')
    tipo = models.ForeignKey(TipoBalancin, on_delete=models.PROTECT, related_name='balancines_individuales')
    
    ESTADOS = [
        ('taller', 'En taller'),
        ('servicio', 'En servicio'),
        ('mantenimiento', 'En mantenimiento'),
        ('baja', 'Dado de baja'),
    ]
    
    estado = models.CharField('Estado', max_length=20, choices=ESTADOS, default='taller')
    fecha_ingreso = models.DateTimeField('Fecha de ingreso', default=timezone.now)
    fecha_ultimo_movimiento = models.DateTimeField('Último movimiento', auto_now=True)
    fecha_salida = models.DateTimeField('Fecha de salida', null=True, blank=True)
    ubicacion_actual = models.CharField('Ubicación', max_length=200, blank=True)
    observaciones = models.TextField('Observaciones', blank=True)
    
    class Meta:
        verbose_name = 'Balancín Individual'
        verbose_name_plural = 'Balancines Individuales'
        ordering = ['tipo', 'serial']
    
    def __str__(self):
        return f"{self.serial} - {self.tipo.codigo} [{self.get_estado_display()}]"

class HistorialBalancin(models.Model):
    """Registra los cambios de estado de los balancines individuales."""
    balancin = models.ForeignKey(BalancinIndividual, on_delete=models.CASCADE, related_name='historial')
    estado_anterior = models.CharField('Estado anterior', max_length=20)
    estado_nuevo = models.CharField('Estado nuevo', max_length=20)
    accion = models.CharField('Acción', max_length=100)
    observaciones = models.TextField('Observaciones', blank=True)
    fecha_cambio = models.DateTimeField('Fecha de cambio', default=timezone.now)
    usuario = models.ForeignKey(Usuario, on_delete=models.SET_NULL, null=True, blank=True)
    
    class Meta:
        verbose_name = 'Historial de Balancín'
        verbose_name_plural = 'Historial de Balancines'
        ordering = ['-fecha_cambio']
    
    def __str__(self):
        return f"{self.balancin.serial} - {self.estado_anterior} → {self.estado_nuevo}"

class RepuestoBalancin(models.Model):
    item = models.CharField('Código', max_length=50, unique=True, primary_key=True, help_text='Ej: REP-BAL-001')
    descripcion = models.TextField('Descripción', max_length=500)
    cantidad = models.PositiveIntegerField('Cantidad', default=0)
    fecha_ingreso = models.DateTimeField('Fecha de ingreso', default=timezone.now)
    fecha_ultimo_movimiento = models.DateTimeField('Último movimiento', auto_now=True)
    fecha_ultima_salida = models.DateTimeField('Última salida', null=True, blank=True)
    ubicacion = models.CharField('Ubicación', max_length=100, blank=True)
    observaciones = models.TextField('Observaciones', blank=True)
    
    class Meta:
        verbose_name = 'Repuesto para Balancín'
        verbose_name_plural = 'Repuestos para Balancines'
        ordering = ['item']
    
    def __str__(self):
        return f"{self.item} - Cantidad: {self.cantidad}"
    
    @property
    def en_stock(self):
        return self.cantidad > 0

class RepuestoAdicional(models.Model):
    item = models.CharField('Código', max_length=50, unique=True, primary_key=True, help_text='Ej: ADIC-001')
    descripcion = models.TextField('Descripción', max_length=500)
    cantidad = models.PositiveIntegerField('Cantidad', default=0)
    fecha_ingreso = models.DateTimeField('Fecha de ingreso', default=timezone.now)
    fecha_ultimo_movimiento = models.DateTimeField('Último movimiento', auto_now=True)
    fecha_ultima_salida = models.DateTimeField('Última salida', null=True, blank=True)
    ubicacion = models.CharField('Ubicación', max_length=100, blank=True)
    observaciones = models.TextField('Observaciones', blank=True)
    
    class Meta:
        verbose_name = 'Repuesto Adicional'
        verbose_name_plural = 'Repuestos Adicionales'
        ordering = ['item']
    
    def __str__(self):
        return f"{self.item} - Cantidad: {self.cantidad}"
    
    @property
    def en_stock(self):
        return self.cantidad > 0

class HistorialRepuesto(models.Model):
    repuesto = models.ForeignKey(RepuestoBalancin, on_delete=models.CASCADE, related_name='historial')
    TIPO_MOVIMIENTO = [('entrada', 'Entrada'), ('salida', 'Salida')]
    tipo_movimiento = models.CharField('Tipo', max_length=20, choices=TIPO_MOVIMIENTO)
    cantidad = models.IntegerField('Cantidad')
    stock_restante = models.PositiveIntegerField('Stock restante')
    observaciones = models.TextField('Observaciones', blank=True)
    fecha_movimiento = models.DateTimeField('Fecha', default=timezone.now)
    
    class Meta:
        verbose_name = 'Historial de Repuesto'
        verbose_name_plural = 'Historial de Repuestos'
        ordering = ['-fecha_movimiento']
    
    def __str__(self):
        return f"{self.repuesto.item} - {self.tipo_movimiento} ({self.cantidad})"
    
    
    
    # Agregar al final de app/models.py

class ActivityLog(models.Model):
    """Modelo para registrar todas las actividades del sistema"""
    
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
        ('USER', 'Usuario'),
        ('SYSTEM', 'Sistema'),
        ('INVENTORY', 'Inventario General'),
    ]
    
    user = models.ForeignKey(
        Usuario, 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True,
        verbose_name="Usuario"
    )
    action = models.CharField(
        max_length=50, 
        choices=ACTION_CHOICES,
        verbose_name="Acción"
    )
    module = models.CharField(
        max_length=50, 
        choices=MODULE_CHOICES,
        verbose_name="Módulo"
    )
    description = models.TextField(
        verbose_name="Descripción detallada"
    )
    
    # Campos para relación con objetos específicos
    object_id = models.CharField(
        max_length=100, 
        null=True, 
        blank=True,
        verbose_name="ID del Objeto"
    )
    object_name = models.CharField(
        max_length=200, 
        null=True, 
        blank=True,
        verbose_name="Nombre del Objeto"
    )
    
    # Campos adicionales para contexto
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    user_agent = models.TextField(null=True, blank=True)
    browser_info = models.CharField(max_length=255, null=True, blank=True)
    
    # Metadata
    created_at = models.DateTimeField(
        default=timezone.now,
        verbose_name="Fecha y hora"
    )
    
    # Campos para cambios específicos (JSON)
    old_values = models.JSONField(null=True, blank=True)
    new_values = models.JSONField(null=True, blank=True)
    
    class Meta:
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
    
    
    # Agrega al final de models.py
class HistorialAdicional(models.Model):
    """Historial para repuestos adicionales"""
    TIPO_MOVIMIENTO = [
        ('entrada', 'Entrada'),
        ('salida', 'Salida'),
        ('creacion', 'Creación'),
        ('actualizacion', 'Actualización'),
    ]
    
    repuesto = models.ForeignKey(RepuestoAdicional, on_delete=models.CASCADE, related_name='historial')
    tipo_movimiento = models.CharField('Tipo', max_length=20, choices=TIPO_MOVIMIENTO)
    cantidad = models.IntegerField('Cantidad')
    stock_restante = models.PositiveIntegerField('Stock restante')
    observaciones = models.TextField('Observaciones', blank=True)
    usuario = models.ForeignKey(Usuario, on_delete=models.SET_NULL, null=True, blank=True)
    fecha_movimiento = models.DateTimeField('Fecha', default=timezone.now)
    
    class Meta:
        verbose_name = 'Historial de Repuesto Adicional'
        verbose_name_plural = 'Historial de Repuestos Adicionales'
        ordering = ['-fecha_movimiento']
    
    def __str__(self):
        return f"{self.repuesto.item} - {self.tipo_movimiento} ({self.cantidad})"