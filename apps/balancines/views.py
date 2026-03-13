from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import login, authenticate
from django.template.loader import render_to_string  # ← ESTO FALTA
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.db.models import Q, Sum, Count, Avg
from django.utils import timezone
from datetime import date
from django.db import transaction
from django.http import HttpResponse, JsonResponse
from openpyxl import Workbook
from openpyxl.styles import Font, PatternFill, Alignment
import json
import re

from .forms import (
    RegistroForm, BalancinIndividualForm, CambiarEstadoForm, 
    TipoBalancinForm, SeleccionarTorreForm, RegistrarOHForm,
    NuevoOHForm
)
from .models import (
    TipoBalancin, BalancinIndividual, HistorialBalancin, BalancinOH,
    RepuestoBalancin, RepuestoAdicional, HistorialRepuesto,   TecnicoFormulario, HistorialAdicional,
    Usuario, Torre, Linea, Seccion, HistorialOH, ActivityLog
)


# ========== VISTAS PRINCIPALES ==========
def home(request):
    """Página de inicio pública."""
    context = {}
    if request.user.is_authenticated:
        context['user'] = request.user
        context['mensaje_bienvenida'] = f'¡Bienvenido de nuevo, {request.user.nombre}!'
    return render(request, 'home.html', context)

@login_required
def dashboard(request):
    """Dashboard principal."""
    total_tipos = TipoBalancin.objects.count()
    total_balancines = BalancinIndividual.objects.count()
    total_repuestos = RepuestoBalancin.objects.count() + RepuestoAdicional.objects.count()
    total_torres = Torre.objects.count()
    
    balancines_asc = BalancinIndividual.objects.filter(sentido='ASCENDENTE').count()
    balancines_desc = BalancinIndividual.objects.filter(sentido='DESCENDENTE').count()
    
    context = {
        'user': request.user,
        'welcome_message': f'Bienvenido, {request.user.nombre}!',
        'total_tipos': total_tipos,
        'total_balancines': total_balancines,
        'total_repuestos': total_repuestos,
        'total_torres': total_torres,
        'balancines_asc': balancines_asc,
        'balancines_desc': balancines_desc,
        'es_jefe': request.user.es_jefe,
        'es_supervisor': request.user.es_supervisor,
        'es_tecnico': request.user.es_tecnico,
    }
    return render(request, 'dashboard.html', context)

def register(request):
    """Vista para registro de usuarios."""
    if request.method == 'POST':
        form = RegistroForm(request.POST)
        if form.is_valid():
            user = form.save()
            user = authenticate(
                email=form.cleaned_data['email'],
                password=form.cleaned_data['password1']
            )
            if user is not None:
                login(request, user)
                messages.success(request, f'¡Bienvenido {user.nombre}! Registro exitoso.')
                return redirect('home')
            else:
                messages.error(request, 'Error al autenticar usuario.')
        else:
            messages.error(request, 'Por favor corrige los errores del formulario.')
    else:
        form = RegistroForm()
    
    context = {'form': form, 'title': 'Registro de Usuario'}
    return render(request, 'accounts/register.html', context)


@login_required
def ultimo_codigo_balancin(request):
    """API para obtener el último código de balancín de un tipo específico."""
    tipo = request.GET.get('tipo', '')
    
    if not tipo:
        return JsonResponse({'error': 'Tipo no especificado'}, status=400)
    
    try:
        balancines = BalancinIndividual.objects.filter(
            codigo__startswith=f"BAL-{tipo}-"
        )
        
        ultimo_numero = 0
        ultimo_codigo = None
        
        for b in balancines:
            partes = b.codigo.split('-')
            if len(partes) >= 4:
                try:
                    numero = int(partes[-1])
                    if numero > ultimo_numero:
                        ultimo_numero = numero
                        ultimo_codigo = b.codigo
                except ValueError:
                    continue
        
        if ultimo_numero == 0:
            ultimo_numero = 0
            siguiente_numero = 1
        else:
            siguiente_numero = ultimo_numero + 1
        
        siguiente_codigo = f"BAL-{tipo}-{siguiente_numero:03d}"
        
        return JsonResponse({
            'tipo': tipo,
            'ultimo_codigo': ultimo_codigo,
            'ultimo_numero': ultimo_numero,
            'siguiente_numero': siguiente_numero,
            'siguiente_codigo': siguiente_codigo
        })
        
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)


# ========== VISTAS DE INVENTARIO ==========
@login_required
def inventario_principal(request):
    """Vista principal del inventario."""
    context = {'title': 'Inventario Principal', 'user': request.user}
    return render(request, 'balancines/inventario_principal.html', context)

@login_required
def lista_tipos_balancin(request):
    """Lista de tipos/modelos de balancín."""
    tipos = TipoBalancin.objects.all().order_by('tipo', 'codigo')
    total_tipos = tipos.count()
    total_cantidad = tipos.aggregate(total=Sum('cantidad_total'))['total'] or 0
    compresion_total = tipos.filter(tipo='compresion').aggregate(total=Sum('cantidad_total'))['total'] or 0
    soporte_total = tipos.filter(tipo='soporte').aggregate(total=Sum('cantidad_total'))['total'] or 0
    
    context = {
        'title': 'Tipos de Balancín',
        'tipos': tipos,
        'total_tipos': total_tipos,
        'total_cantidad': total_cantidad,
        'compresion_total': compresion_total,
        'soporte_total': soporte_total,
    }
    return render(request, 'balancines/tipos_balancin.html', context)



@login_required
def detalle_tipo_balancin(request, codigo):
    """Detalle de un tipo de balancín con sus balancines individuales en torres."""
    tipo = get_object_or_404(TipoBalancin, codigo=codigo)
    
    # Buscar TODOS los balancines de ESTE tipo instalados en torres
    balancines = BalancinIndividual.objects.filter(
        Q(torre__tipo_balancin_ascendente=codigo) |
        Q(torre__tipo_balancin_descendente=codigo)
    ).select_related(
        'torre', 
        'torre__linea', 
        'torre__seccion'
    ).prefetch_related(
        'historial_oh_completo'
    ).order_by('torre__linea_id', 'torre__numero_torre')
    
    balancines_asc = [b for b in balancines if b.sentido == 'ASCENDENTE']
    balancines_desc = [b for b in balancines if b.sentido == 'DESCENDENTE']
    
    torres_ascendentes = Torre.objects.filter(
        tipo_balancin_ascendente=codigo
    ).select_related('linea', 'seccion')
    
    torres_descendentes = Torre.objects.filter(
        tipo_balancin_descendente=codigo
    ).select_related('linea', 'seccion')
    
    torres_con_ascendente = set(
        BalancinIndividual.objects.filter(
            torre__in=torres_ascendentes,
            sentido='ASCENDENTE'
        ).values_list('torre_id', flat=True)
    )
    
    torres_con_descendente = set(
        BalancinIndividual.objects.filter(
            torre__in=torres_descendentes,
            sentido='DESCENDENTE'
        ).values_list('torre_id', flat=True)
    )
    
    context = {
        'title': f'Tipo: {codigo}',
        'tipo': tipo,
        'balancines': balancines,
        'balancines_asc': balancines_asc,
        'balancines_desc': balancines_desc,
        'total_balancines': balancines.count(),
        'torres_ascendentes': torres_ascendentes,
        'torres_descendentes': torres_descendentes,
        'torres_con_ascendente': torres_con_ascendente,
        'torres_con_descendente': torres_con_descendente,
    }
    return render(request, 'balancines/detalle_tipo_balancin.html', context)

@login_required
def lista_balancines_individuales(request):
    """Lista de balancines individuales instalados en torres."""
    balancines = BalancinIndividual.objects.all().select_related(
        'torre', 'torre__linea', 'torre__seccion'
    ).prefetch_related('ordenes_horas').order_by('torre__linea_id', 'torre__numero_torre')
    
    sentido = request.GET.get('sentido', '')
    linea_id = request.GET.get('linea', '')
    
    if sentido:
        balancines = balancines.filter(sentido=sentido)
    if linea_id:
        balancines = balancines.filter(torre__linea_id=linea_id)
    
    total_balancines = balancines.count()
    lineas = Linea.objects.all()
    
    context = {
        'title': 'Balancines Individuales',
        'balancines': balancines,
        'total_balancines': total_balancines,
        'lineas': lineas,
        'sentido_filtro': sentido,
        'linea_filtro': linea_id,
    }
    return render(request, 'balancines/balancines_individuales.html', context)

@login_required
def detalle_balancin(request, codigo):
    """Detalle de un balancín individual."""
    balancin = get_object_or_404(
        BalancinIndividual.objects.select_related(
            'torre', 'torre__linea', 'torre__seccion'
        ),
        codigo=codigo
    )
    historial = balancin.historial.all().order_by('-fecha_cambio')[:10]
    ordenes_horas = balancin.ordenes_horas.all().order_by('-numero_oh')[:5]
    
    # Obtener formularios de control asociados
    formularios = FormularioControlOH.objects.filter(
        balancin=balancin
    ).order_by('-fecha')[:5]
    
    context = {
        'title': f'Balancín {codigo}',
        'balancin': balancin,
        'historial': historial,
        'ordenes_horas': ordenes_horas,
        'formularios': formularios,
        'tipo_codigo': balancin.tipo_balancin_codigo,
    }
    return render(request, 'balancines/detalle_balancin.html', context)


# ========== VISTAS PARA AGREGAR ==========
@login_required
def agregar_tipo_balancin(request):
    """Vista para agregar un nuevo tipo de balancín."""
    if request.method == 'POST':
        form = TipoBalancinForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, f'Tipo de balancín {form.cleaned_data["codigo"]} agregado correctamente.')
            return redirect('lista_tipos_balancin')
    else:
        form = TipoBalancinForm()
    
    context = {'title': 'Agregar Tipo de Balancín', 'form': form}
    return render(request, 'balancines/agregar_tipo_balancin.html', context)

@login_required
def agregar_balancin_individual(request):
    """Vista para agregar un balancín individual en una torre."""
    tipo_predefinido = request.GET.get('tipo', '')
    torre_id = request.GET.get('torre', '')
    sentido_predefinido = request.GET.get('sentido', 'ASCENDENTE')
    
    torre_seleccionada = None
    if torre_id:
        try:
            torre_seleccionada = Torre.objects.select_related('linea', 'seccion').get(id=torre_id)
        except Torre.DoesNotExist:
            pass
    
    if request.method == 'POST':
        form = BalancinIndividualForm(request.POST)
        if form.is_valid():
            balancin = form.save(commit=False)
            
            if torre_seleccionada:
                balancin.torre = torre_seleccionada
            
            balancin.save()
            
            try:
                HistorialBalancin.objects.create(
                    balancin=balancin,
                    estado_anterior='NUEVO',
                    estado_nuevo='INSTALADO',
                    accion='INSTALACION',
                    observaciones=f'Balancín instalado en {balancin.torre}',
                    usuario=request.user
                )
            except Exception as e:
                print(f"Error al crear historial: {e}")
            
            messages.success(request, f'✅ Balancín {balancin.codigo} instalado correctamente en {balancin.torre}.')
            
            tipo_codigo = balancin.tipo_balancin_codigo
            if tipo_codigo:
                return redirect('detalle_tipo_balancin', codigo=tipo_codigo)
            else:
                return redirect('lista_tipos_balancin')
        else:
            messages.error(request, '❌ Por favor corrige los errores del formulario.')
            for field, errors in form.errors.items():
                for error in errors:
                    messages.error(request, f'{field}: {error}')
    else:
        initial = {
            'sentido': sentido_predefinido,
            'rango_horas_cambio_oh': 30000
        }
        if torre_seleccionada:
            initial['torre'] = torre_seleccionada
        
        form = BalancinIndividualForm(initial=initial)
    
    context = {
        'title': 'Instalar Balancín Individual',
        'form': form,
        'tipo_predefinido': tipo_predefinido,
        'torre_seleccionada': torre_seleccionada,
        'sentido_predefinido': sentido_predefinido,
    }
    return render(request, 'balancines/agregar_balancin_individual.html', context)


# ========== VISTAS PARA REGISTRAR OH ==========
@login_required
def registrar_oh_balancin(request, codigo):
    """Registrar una orden de horas para un balancín."""
    balancin = get_object_or_404(BalancinIndividual, codigo=codigo)
    
    if request.method == 'POST':
        form = RegistrarOHForm(request.POST)
        if form.is_valid():
            numero_oh = form.cleaned_data['numero_oh']
            
            if BalancinOH.objects.filter(balancin=balancin, numero_oh=numero_oh).exists():
                messages.error(request, f'Ya existe la OH #{numero_oh} para este balancín.')
            else:
                oh = BalancinOH.objects.create(
                    balancin=balancin,
                    numero_oh=numero_oh,
                    fecha_oh=form.cleaned_data['fecha_oh'],
                    horas_operacion=form.cleaned_data['horas_operacion'],
                    observaciones=form.cleaned_data['observaciones']
                )
                messages.success(request, f'OH #{numero_oh} registrada correctamente.')
                return redirect('detalle_balancin', codigo=balancin.codigo)
    else:
        ultimo_oh = balancin.ordenes_horas.order_by('-numero_oh').first()
        next_oh = (ultimo_oh.numero_oh + 1) if ultimo_oh else 1
        form = RegistrarOHForm(initial={
            'numero_oh': next_oh,
            'fecha_oh': timezone.now().date()
        })
    
    context = {
        'title': f'Registrar OH - {balancin.codigo}',
        'form': form,
        'balancin': balancin,
    }
    return render(request, 'balancines/registrar_oh.html', context)

@login_required
def editar_balancin_individual(request, codigo):
    """Vista para editar un balancín individual."""
    balancin = get_object_or_404(BalancinIndividual, codigo=codigo)
    
    if request.method == 'POST':
        form = BalancinIndividualForm(request.POST, instance=balancin)
        if form.is_valid():
            balancin_editado = form.save()
            messages.success(request, f'✅ Balancín {balancin_editado.codigo} actualizado correctamente.')
            
            tipo_codigo = balancin_editado.tipo_balancin_codigo
            if tipo_codigo:
                return redirect('detalle_tipo_balancin', codigo=tipo_codigo)
            else:
                return redirect('lista_tipos_balancin')
        else:
            messages.error(request, '❌ Por favor corrige los errores del formulario.')
    else:
        form = BalancinIndividualForm(instance=balancin)
    
    context = {
        'title': f'Editar Balancín - {balancin.codigo}',
        'form': form,
        'balancin': balancin,
    }
    return render(request, 'balancines/editar_balancin_individual.html', context)


# ========== VISTAS DE ELIMINACIÓN ==========
@login_required
def eliminar_balancin_individual(request, codigo):
    """Vista para eliminar un balancín individual."""
    balancin = get_object_or_404(BalancinIndividual, codigo=codigo)
    tipo_codigo = balancin.tipo_balancin_codigo
    
    if request.method == 'POST':
        balancin.delete()
        messages.success(request, f'Balancín {codigo} eliminado correctamente.')
        return redirect('detalle_tipo_balancin', codigo=tipo_codigo)
    
    context = {
        'title': f'Eliminar Balancín: {codigo}',
        'balancin': balancin
    }
    return render(request, 'balancines/confirmar_eliminacion.html', context)


# ========== VISTAS DE REPUESTOS ==========
@login_required
def lista_repuestos_balancin(request):
    """Lista de repuestos para balancines."""
    repuestos = RepuestoBalancin.objects.all().order_by('item')
    stock = request.GET.get('stock', '')
    query = request.GET.get('q', '')

    if query:
        repuestos = repuestos.filter(
            Q(item__icontains=query) | Q(descripcion__icontains=query) |
            Q(ubicacion__icontains=query) | Q(observaciones__icontains=query)
        )

    if stock == 'bajo':
        repuestos = repuestos.filter(cantidad__lt=5, cantidad__gt=0)
    elif stock == 'agotado':
        repuestos = repuestos.filter(cantidad=0)

    total_repuestos = repuestos.count()
    total_cantidad = repuestos.aggregate(total=Sum('cantidad'))['total'] or 0
    
    repuestos_bajo_stock = RepuestoBalancin.objects.filter(cantidad__lt=5, cantidad__gt=0)
    repuestos_sin_stock = RepuestoBalancin.objects.filter(cantidad=0)
    
    ultimas_actividades = get_ultimas_actividades_repuestos(request)

    context = {
        'title': 'Repuestos para Balancines',
        'repuestos': repuestos,
        'total_repuestos': total_repuestos,
        'total_cantidad': total_cantidad,
        'repuestos_bajo_stock': repuestos_bajo_stock,
        'repuestos_sin_stock': repuestos_sin_stock,
        'stock_filtro': stock,
        'query': query,
        'ultimas_actividades': ultimas_actividades,
    }
    return render(request, 'balancines/repuestos_balancin.html', context)

@login_required
def lista_repuestos_adicionales(request):
    """Lista de repuestos adicionales."""
    repuestos = RepuestoAdicional.objects.all().order_by('item')
    
    stock = request.GET.get('stock', '')
    query = request.GET.get('q', '')
    
    if query:
        repuestos = repuestos.filter(
            Q(item__icontains=query) | 
            Q(descripcion__icontains=query) |
            Q(ubicacion__icontains=query) |
            Q(observaciones__icontains=query)
        )
    
    if stock == 'bajo':
        repuestos = repuestos.filter(cantidad__lt=5, cantidad__gt=0)
    elif stock == 'agotado':
        repuestos = repuestos.filter(cantidad=0)
    
    total_repuestos = repuestos.count()
    total_cantidad = repuestos.aggregate(total=Sum('cantidad'))['total'] or 0
    
    repuestos_bajo_stock = RepuestoAdicional.objects.filter(cantidad__lt=5, cantidad__gt=0)
    repuestos_sin_stock = RepuestoAdicional.objects.filter(cantidad=0)
    
    ultimas_actividades = get_ultimas_actividades_adicionales(request)
    
    context = {
        'title': 'Repuestos Adicionales',
        'repuestos': repuestos,
        'total_repuestos': total_repuestos,
        'total_cantidad': total_cantidad,
        'repuestos_bajo_stock': repuestos_bajo_stock,
        'repuestos_sin_stock': repuestos_sin_stock,
        'stock_filtro': stock,
        'query': query,
        'ultimas_actividades': ultimas_actividades,
    }
    return render(request, 'balancines/repuestos_adicionales.html', context)

@login_required
def agregar_repuesto_balancin(request):
    """Vista para agregar un repuesto para balancín."""
    if request.method == 'POST':
        item = request.POST.get('item', '').strip()
        descripcion = request.POST.get('descripcion', '').strip()
        cantidad = int(request.POST.get('cantidad', 0) or 0)
        ubicacion = request.POST.get('ubicacion', '').strip()
        observaciones = request.POST.get('observaciones', '')
        
        if not item:
            messages.error(request, 'El código del item es requerido.')
        elif RepuestoBalancin.objects.filter(item=item).exists():
            messages.error(request, f'El item {item} ya existe.')
        else:
            RepuestoBalancin.objects.create(
                item=item.upper(),
                descripcion=descripcion,
                cantidad=cantidad,
                ubicacion=ubicacion,
                observaciones=observaciones
            )
            messages.success(request, f'Repuesto {item} agregado correctamente.')
            return redirect('lista_repuestos_balancin')
    
    context = {'title': 'Agregar Repuesto para Balancín'}
    return render(request, 'balancines/form_repuesto_balancin.html', context)

@login_required
def agregar_repuesto_adicional(request):
    """Vista para agregar un repuesto adicional."""
    if request.method == 'POST':
        item = request.POST.get('item', '').strip()
        descripcion = request.POST.get('descripcion', '').strip()
        cantidad = int(request.POST.get('cantidad', 0) or 0)
        ubicacion = request.POST.get('ubicacion', '').strip()
        observaciones = request.POST.get('observaciones', '')
        
        if not item:
            messages.error(request, 'El código del item es requerido.')
        elif RepuestoAdicional.objects.filter(item=item).exists():
            messages.error(request, f'El item {item} ya existe.')
        else:
            repuesto = RepuestoAdicional.objects.create(
                item=item.upper(),
                descripcion=descripcion,
                cantidad=cantidad,
                ubicacion=ubicacion,
                observaciones=observaciones
            )
            
            try:
                HistorialAdicional.objects.create(
                    repuesto=repuesto,
                    tipo_movimiento='creacion',
                    cantidad=cantidad,
                    stock_restante=cantidad,
                    observaciones='Creación inicial del repuesto',
                    usuario=request.user
                )
            except Exception as e:
                print(f"Error al registrar creación: {e}")
            
            messages.success(request, f'Repuesto adicional {item} agregado correctamente.')
            return redirect('lista_repuestos_adicionales')
    
    context = {'title': 'Agregar Repuesto Adicional'}
    return render(request, 'balancines/form_repuesto_adicional.html', context)


# ========== VISTAS PARA MANEJO DE STOCK ==========
@login_required
def entrada_stock_adicional(request, item):
    """Registrar entrada de stock para repuesto adicional."""
    repuesto = get_object_or_404(RepuestoAdicional, item=item)
    
    if request.method == 'POST':
        cantidad = int(request.POST.get('cantidad', 0) or 0)
        observaciones = request.POST.get('observaciones', '').strip()
        
        if cantidad <= 0:
            messages.error(request, '❌ La cantidad debe ser mayor a 0.')
        else:
            stock_anterior = repuesto.cantidad
            repuesto.cantidad += cantidad
            repuesto.fecha_ultimo_movimiento = timezone.now()
            repuesto.save()
            
            try:
                HistorialAdicional.objects.create(
                    repuesto=repuesto,
                    tipo_movimiento='entrada',
                    cantidad=cantidad,
                    stock_restante=repuesto.cantidad,
                    observaciones=f'Entrada de {cantidad} unidades. {observaciones}',
                    usuario=request.user
                )
            except Exception as e:
                print(f"Error al crear historial adicional: {e}")
            
            messages.success(request, 
                f'✅ Entrada registrada: {stock_anterior} → {repuesto.cantidad} unidades (+{cantidad})')
            return redirect('lista_repuestos_adicionales')
    
    context = {
        'title': f'Entrada de Stock: {item}',
        'repuesto': repuesto,
    }
    return render(request, 'balancines/entrada_stock_adicional.html', context)

@login_required
def salida_stock_adicional(request, item):
    """Registrar salida de stock para repuesto adicional."""
    repuesto = get_object_or_404(RepuestoAdicional, item=item)
    
    if request.method == 'POST':
        cantidad = int(request.POST.get('cantidad', 0) or 0)
        observaciones = request.POST.get('observaciones', '').strip()
        
        if cantidad <= 0:
            messages.error(request, '❌ La cantidad debe ser mayor a 0.')
        elif cantidad > repuesto.cantidad:
            messages.error(request, f'❌ Stock insuficiente. Disponible: {repuesto.cantidad}')
        else:
            stock_anterior = repuesto.cantidad
            repuesto.cantidad -= cantidad
            repuesto.fecha_ultimo_movimiento = timezone.now()
            repuesto.fecha_ultima_salida = timezone.now()
            repuesto.save()
            
            try:
                HistorialAdicional.objects.create(
                    repuesto=repuesto,
                    tipo_movimiento='salida',
                    cantidad=cantidad,
                    stock_restante=repuesto.cantidad,
                    observaciones=f'Salida de {cantidad} unidades. {observaciones}',
                    usuario=request.user
                )
            except Exception as e:
                print(f"Error al crear historial adicional: {e}")
            
            messages.success(request, 
                f'✅ Salida registrada: {stock_anterior} → {repuesto.cantidad} unidades (-{cantidad})')
            return redirect('lista_repuestos_adicionales')
    
    context = {
        'title': f'Salida de Stock: {item}',
        'repuesto': repuesto,
    }
    return render(request, 'balancines/salida_stock_adicional.html', context)

@login_required
def entrada_stock_balancin(request, item):
    """Registrar entrada de stock para repuesto de balancín."""
    repuesto = get_object_or_404(RepuestoBalancin, item=item)
    
    if request.method == 'POST':
        cantidad = int(request.POST.get('cantidad', 0) or 0)
        observaciones = request.POST.get('observaciones', '').strip()
        
        if cantidad <= 0:
            messages.error(request, '❌ La cantidad debe ser mayor a 0.')
        else:
            stock_anterior = repuesto.cantidad
            repuesto.cantidad += cantidad
            repuesto.fecha_ultimo_movimiento = timezone.now()
            repuesto.save()
            
            try:
                HistorialRepuesto.objects.create(
                    repuesto=repuesto,
                    tipo_movimiento='entrada',
                    cantidad=cantidad,
                    stock_restante=repuesto.cantidad,
                    observaciones=f'Entrada de {cantidad} unidades. {observaciones}'
                )
            except:
                pass
            
            messages.success(request, 
                f'✅ Entrada registrada: {stock_anterior} → {repuesto.cantidad} unidades (+{cantidad})')
            return redirect('lista_repuestos_balancin')
    
    context = {
        'title': f'Entrada de Stock: {item}',
        'repuesto': repuesto,
    }
    return render(request, 'balancines/entrada_stock_balancin.html', context)

@login_required
def salida_stock_balancin(request, item):
    """Registrar salida de stock para repuesto de balancín."""
    repuesto = get_object_or_404(RepuestoBalancin, item=item)
    
    if request.method == 'POST':
        cantidad = int(request.POST.get('cantidad', 0) or 0)
        observaciones = request.POST.get('observaciones', '').strip()
        
        if cantidad <= 0:
            messages.error(request, '❌ La cantidad debe ser mayor a 0.')
        elif cantidad > repuesto.cantidad:
            messages.error(request, f'❌ Stock insuficiente. Disponible: {repuesto.cantidad}')
        else:
            stock_anterior = repuesto.cantidad
            repuesto.cantidad -= cantidad
            repuesto.fecha_ultimo_movimiento = timezone.now()
            repuesto.fecha_ultima_salida = timezone.now()
            repuesto.save()
            
            try:
                HistorialRepuesto.objects.create(
                    repuesto=repuesto,
                    tipo_movimiento='salida',
                    cantidad=cantidad,
                    stock_restante=repuesto.cantidad,
                    observaciones=f'Salida de {cantidad} unidades. {observaciones}'
                )
            except:
                pass
            
            messages.success(request, 
                f'✅ Salida registrada: {stock_anterior} → {repuesto.cantidad} unidades (-{cantidad})')
            return redirect('lista_repuestos_balancin')
    
    context = {
        'title': f'Salida de Stock: {item}',
        'repuesto': repuesto,
    }
    return render(request, 'balancines/salida_stock_balancin.html', context)


# ========== DASHBOARD ==========
@login_required
def dashboard_inventario(request):
    """Dashboard con estadísticas del inventario."""
    
    total_tipos = TipoBalancin.objects.count()
    total_balancines = BalancinIndividual.objects.count()
    total_torres = Torre.objects.count()
    total_lineas = Linea.objects.count()
    
    balancines_asc = BalancinIndividual.objects.filter(sentido='ASCENDENTE').count()
    balancines_desc = BalancinIndividual.objects.filter(sentido='DESCENDENTE').count()
    
    repuestos_balancin = RepuestoBalancin.objects.count()
    repuestos_adicional = RepuestoAdicional.objects.count()
    total_repuestos = repuestos_balancin + repuestos_adicional
    
    repuestos_bajo_stock = list(RepuestoBalancin.objects.filter(cantidad__lt=5, cantidad__gt=0)) + \
                          list(RepuestoAdicional.objects.filter(cantidad__lt=5, cantidad__gt=0))
    repuestos_sin_stock = list(RepuestoBalancin.objects.filter(cantidad=0)) + \
                         list(RepuestoAdicional.objects.filter(cantidad=0))
    repuestos_normal = total_repuestos - len(repuestos_bajo_stock) - len(repuestos_sin_stock)
    
    balancines_criticos = 0
    balancines_alerta = 0
    balancines_normal = 0
    balancines_sin_oh = 0
    
    for b in BalancinIndividual.objects.all():
        ultima_oh = b.ordenes_horas.order_by('-numero_oh').first()
        if not ultima_oh:
            balancines_sin_oh += 1
        else:
            porcentaje = (ultima_oh.horas_operacion / b.rango_horas_cambio_oh) * 100
            if ultima_oh.horas_operacion >= b.rango_horas_cambio_oh:
                balancines_criticos += 1
            elif porcentaje >= 80:
                balancines_alerta += 1
            else:
                balancines_normal += 1
    
    total_con_oh = balancines_criticos + balancines_alerta + balancines_normal
    porcentaje_normal = (balancines_normal / total_con_oh * 100) if total_con_oh > 0 else 0
    porcentaje_alerta = (balancines_alerta / total_con_oh * 100) if total_con_oh > 0 else 0
    porcentaje_critico = (balancines_criticos / total_con_oh * 100) if total_con_oh > 0 else 0
    
    context = {
        'title': 'Dashboard de Inventario',
        'total_tipos': total_tipos,
        'total_balancines': total_balancines,
        'balancines_asc': balancines_asc,
        'balancines_desc': balancines_desc,
        'total_torres': total_torres,
        'total_lineas': total_lineas,
        'total_repuestos': total_repuestos,
        'repuestos_balancin': repuestos_balancin,
        'repuestos_adicional': repuestos_adicional,
        'repuestos_bajo_stock': repuestos_bajo_stock[:10],
        'repuestos_sin_stock': repuestos_sin_stock[:10],
        'repuestos_normal': repuestos_normal,
        'balancines_criticos': balancines_criticos,
        'balancines_alerta': balancines_alerta,
        'balancines_normal': balancines_normal,
        'balancines_sin_oh': balancines_sin_oh,
        'porcentaje_normal': porcentaje_normal,
        'porcentaje_alerta': porcentaje_alerta,
        'porcentaje_critico': porcentaje_critico,
    }
    return render(request, 'balancines/dashboard_inventario.html', context)


@login_required
def buscar_inventario(request):
    """Búsqueda mejorada en todo el inventario."""
    query = request.GET.get('q', '').strip()
    tipo = request.GET.get('tipo', '')
    
    resultados = {
        'tipos': [],
        'balancines': [],
        'torres': [],
        'repuestos_balancin': [],
        'repuestos_adicionales': [],
    }
    
    total_resultados = 0
    
    if query:
        query_upper = query.upper()
        
        # ===== 1. BÚSQUEDA EN TIPOS DE BALANCÍN =====
        if not tipo or tipo == 'tipos':
            resultados['tipos'] = TipoBalancin.objects.filter(
                Q(codigo__icontains=query_upper) | 
                Q(tipo__icontains=query)
            )[:10]
            total_resultados += len(resultados['tipos'])
        
        # ===== 2. BÚSQUEDA EN BALANCINES INDIVIDUALES =====
        if not tipo or tipo == 'balancines':
            resultados['balancines'] = BalancinIndividual.objects.filter(
                Q(codigo__icontains=query_upper)
            ).select_related(
                'torre', 'torre__linea', 'torre__seccion'
            )[:20]
            
            # Agregar información adicional a cada balancín
            for b in resultados['balancines']:
                # Último OH
                ultimo_oh = HistorialOH.objects.filter(balancin=b).order_by('-numero_oh').first()
                b.ultimo_oh = ultimo_oh
                
                # Calcular estado
                if ultimo_oh:
                    if ultimo_oh.backlog < 0:
                        b.estado_color = 'danger'
                        b.estado_texto = 'Crítico'
                    elif ultimo_oh.backlog < 5000:
                        b.estado_color = 'warning'
                        b.estado_texto = 'Alerta'
                    else:
                        b.estado_color = 'success'
                        b.estado_texto = 'Normal'
                else:
                    b.estado_color = 'secondary'
                    b.estado_texto = 'Sin OH'
            
            total_resultados += len(resultados['balancines'])
        
        # ===== 3. BÚSQUEDA EN TORRES =====
        if not tipo or tipo == 'torres':
            palabras = query.split()
            
            filtros = Q()
            for palabra in palabras:
                if palabra.isdigit():
                    filtros |= Q(numero_torre=palabra)
                else:
                    filtros |= Q(tipo_balancin_ascendente__icontains=palabra) | \
                               Q(tipo_balancin_descendente__icontains=palabra)
            
            torres_query = Torre.objects.filter(filtros).select_related('linea', 'seccion')
            
            for torre in torres_query:
                torre.total_balancines = BalancinIndividual.objects.filter(torre=torre).count()
                torre.ascendentes = BalancinIndividual.objects.filter(torre=torre, sentido='ASCENDENTE').count()
                torre.descendentes = torre.total_balancines - torre.ascendentes
            
            resultados['torres'] = torres_query
            total_resultados += torres_query.count()
        
        # ===== 4. BÚSQUEDA EN REPUESTOS PARA BALANCINES =====
        if not tipo or tipo == 'repuestos':
            resultados['repuestos_balancin'] = RepuestoBalancin.objects.filter(
                Q(item__icontains=query_upper) | 
                Q(descripcion__icontains=query) |
                Q(ubicacion__icontains=query)
            )[:20]
            total_resultados += len(resultados['repuestos_balancin'])
        
        # ===== 5. BÚSQUEDA EN REPUESTOS ADICIONALES =====
        if not tipo or tipo == 'adicionales':
            resultados['repuestos_adicionales'] = RepuestoAdicional.objects.filter(
                Q(item__icontains=query_upper) | 
                Q(descripcion__icontains=query) |
                Q(ubicacion__icontains=query)
            )[:20]
            total_resultados += len(resultados['repuestos_adicionales'])

    context = {
        'title': 'Buscar en Inventario',
        'query': query,
        'tipo_filtro': tipo,
        'resultados': resultados,
        'total_resultados': total_resultados,
        'tiene_resultados': total_resultados > 0,
    }
    return render(request, 'balancines/buscar_inventario.html', context)


# ========== FUNCIONES AUXILIARES ==========
def get_ultimas_actividades_repuestos(request):
    """Obtiene las últimas actividades de repuestos."""
    actividades = []
    
    try:
        historiales = HistorialRepuesto.objects.select_related('repuesto').order_by('-fecha_movimiento')[:10]
        for h in historiales:
            actividades.append({
                'fecha': h.fecha_movimiento,
                'tipo': h.tipo_movimiento,
                'repuesto': h.repuesto.item,
                'cantidad': h.cantidad,
                'stock_restante': h.stock_restante,
                'observaciones': h.observaciones,
                'tipo_actividad': 'movimiento_stock',
                'icono': 'fa-exchange-alt' if h.tipo_movimiento == 'entrada' else 'fa-external-link-alt',
                'color': 'success' if h.tipo_movimiento == 'entrada' else 'danger'
            })
    except:
        pass
    
    actividades.sort(key=lambda x: x['fecha'], reverse=True)
    return actividades[:5]

def get_ultimas_actividades_adicionales(request):
    """Obtiene las últimas actividades de repuestos adicionales."""
    actividades = []
    
    try:
        historiales = HistorialAdicional.objects.select_related('repuesto', 'usuario').order_by('-fecha_movimiento')[:15]
        
        for h in historiales:
            actividades.append({
                'fecha': h.fecha_movimiento,
                'tipo': h.tipo_movimiento,
                'repuesto': h.repuesto.item,
                'cantidad': h.cantidad,
                'stock_restante': h.stock_restante,
                'observaciones': h.observaciones,
                'usuario': h.usuario.nombre if h.usuario else 'Sistema',
            })
    except Exception as e:
        print(f"ERROR en get_ultimas_actividades_adicionales: {e}")
    
    actividades.sort(key=lambda x: x['fecha'], reverse=True)
    return actividades[:5]


# ========== EXPORTAR EXCEL ==========
@login_required
def exportar_inventario_excel(request):
    """Exporta TODO el inventario a un archivo Excel."""
    wb = Workbook()

    # HOJA 1 — Balancines Individuales
    ws = wb.active
    ws.title = "Balancines en Torres"
    
    headers = ["Código", "Línea", "Torre", "Sección", "Sentido", "Rango OH", "Fecha Instalación"]
    ws.append(headers)
    
    for cell in ws[1]:
        cell.font = Font(bold=True)
    
    for b in BalancinIndividual.objects.select_related('torre', 'torre__linea', 'torre__seccion'):
        ws.append([
            b.codigo,
            b.torre.linea.nombre if b.torre.linea else "",
            b.torre.numero_torre,
            b.torre.seccion.nombre if b.torre.seccion else "",
            b.get_sentido_display(),
            b.rango_horas_cambio_oh,
            b.fecha_registro.strftime('%d/%m/%Y') if b.fecha_registro else ""
        ])
    
    ws.auto_filter.ref = ws.dimensions

    # HOJA 2 — Tipos de Balancín
    ws2 = wb.create_sheet("Tipos")
    ws2.append(["Código", "Tipo", "Cantidad Total"])
    
    for cell in ws2[1]:
        cell.font = Font(bold=True)
    
    for t in TipoBalancin.objects.all():
        ws2.append([t.codigo, t.get_tipo_display(), t.cantidad_total])
    
    ws2.auto_filter.ref = ws2.dimensions

    # HOJA 3 — Repuestos Balancín
    ws3 = wb.create_sheet("Repuestos Balancin")
    ws3.append(["Item", "Descripción", "Cantidad", "Ubicación", "Observaciones"])
    
    for cell in ws3[1]:
        cell.font = Font(bold=True)
    
    for r in RepuestoBalancin.objects.all():
        ws3.append([r.item, r.descripcion, r.cantidad, r.ubicacion, r.observaciones])
    
    ws3.auto_filter.ref = ws3.dimensions

    # HOJA 4 — Repuestos Adicionales
    ws4 = wb.create_sheet("Repuestos Adicionales")
    ws4.append(["Item", "Descripción", "Cantidad", "Ubicación", "Observaciones"])
    
    for cell in ws4[1]:
        cell.font = Font(bold=True)
    
    for r in RepuestoAdicional.objects.all():
        ws4.append([r.item, r.descripcion, r.cantidad, r.ubicacion, r.observaciones])
    
    ws4.auto_filter.ref = ws4.dimensions

    response = HttpResponse(
        content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
    )
    response['Content-Disposition'] = 'attachment; filename=inventario_completo.xlsx'
    wb.save(response)
    return response



@login_required
def exportar_oh_excel(request):
    """Exportar historial de OH a Excel"""
    from openpyxl.styles import Font, Alignment, PatternFill
    
    wb = Workbook()
    ws = wb.active
    ws.title = "Historial OH"
    
    headers = [
        "Línea", "Sección", "Torre", "Sentido", "Código", "Tipo", "Rango OH",
        "OH1 Fecha", "OH1 Año", "OH1 Horas", "OH1 Backlog",
        "OH2 Fecha", "OH2 Año", "OH2 Horas", "OH2 Backlog",
        "OH3 Fecha", "OH3 Año", "OH3 Horas", "OH3 Backlog",
        "OH4 Fecha", "OH4 Año", "OH4 Horas", "OH4 Backlog",
        "Estado"
    ]
    
    ws.append(headers)
    
    for cell in ws[1]:
        cell.font = Font(bold=True, color="FFFFFF")
        cell.fill = PatternFill(start_color="4E73DF", end_color="4E73DF", fill_type="solid")
        cell.alignment = Alignment(horizontal="center")
    
    balancines = BalancinIndividual.objects.select_related(
        'torre', 'torre__linea', 'torre__seccion'
    ).prefetch_related('ordenes_horas').all()
    
    for b in balancines[:1000]:
        ohs = b.ordenes_horas.order_by('numero_oh')
        
        ultima_oh = ohs.last()
        if not ultima_oh:
            estado = "Sin OH"
        elif ultima_oh.horas_operacion >= b.rango_horas_cambio_oh:
            estado = "Crítico"
        elif (ultima_oh.horas_operacion / b.rango_horas_cambio_oh) >= 0.8:
            estado = "Alerta"
        else:
            estado = "Normal"
        
        row = [
            b.torre.linea.nombre,
            b.torre.seccion.nombre,
            b.torre.numero_torre,
            b.get_sentido_display(),
            b.codigo,
            b.tipo_balancin_codigo,
            b.rango_horas_cambio_oh,
            
            ohs[0].fecha_oh.strftime('%b-%y') if len(ohs) > 0 else "",
            ohs[0].fecha_oh.year if len(ohs) > 0 else "",
            ohs[0].horas_operacion if len(ohs) > 0 else "",
            (ohs[0].horas_operacion - b.rango_horas_cambio_oh) if len(ohs) > 0 else "",
            
            ohs[1].fecha_oh.strftime('%b-%y') if len(ohs) > 1 else "",
            ohs[1].fecha_oh.year if len(ohs) > 1 else "",
            ohs[1].horas_operacion if len(ohs) > 1 else "",
            (ohs[1].horas_operacion - b.rango_horas_cambio_oh) if len(ohs) > 1 else "",
            
            ohs[2].fecha_oh.strftime('%b-%y') if len(ohs) > 2 else "",
            ohs[2].fecha_oh.year if len(ohs) > 2 else "",
            ohs[2].horas_operacion if len(ohs) > 2 else "",
            (ohs[2].horas_operacion - b.rango_horas_cambio_oh) if len(ohs) > 2 else "",
            
            ohs[3].fecha_oh.strftime('%b-%y') if len(ohs) > 3 else "",
            ohs[3].fecha_oh.year if len(ohs) > 3 else "",
            ohs[3].horas_operacion if len(ohs) > 3 else "",
            (ohs[3].horas_operacion - b.rango_horas_cambio_oh) if len(ohs) > 3 else "",
            
            estado
        ]
        ws.append(row)
    
    for column in ws.columns:
        max_length = 0
        column_letter = column[0].column_letter
        for cell in column:
            try:
                if len(str(cell.value)) > max_length:
                    max_length = len(str(cell.value))
            except:
                pass
        adjusted_width = min(max_length + 2, 30)
        ws.column_dimensions[column_letter].width = adjusted_width
    
    response = HttpResponse(
        content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
    )
    response['Content-Disposition'] = 'attachment; filename=historial_oh_balancines.xlsx'
    wb.save(response)
    
    return response


@login_required
def dashboard_oh_nuevo(request):
    """Dashboard con gráficos de estado por torre y listado detallado"""
    
    # ===== OBTENER FILTROS =====
    linea_filtro = request.GET.get('linea', '')
    torre_filtro = request.GET.get('torre', '')
    estado_filtro = request.GET.get('estado', '')
    balancin_filtro = request.GET.get('balancin', '')
    
    # ===== PARTE 1: DATOS PARA FILTROS =====
    lineas = Linea.objects.all().order_by('nombre')
    tipos = TipoBalancin.objects.all().order_by('codigo')
    
    # ===== PARTE 2: OBTENER DATOS AGRUPADOS POR BALANCÍN =====
    from django.db import connection
    import json
    
    # Consulta para obtener todos los OH dinámicamente
    query = """
        SELECT 
            linea_nombre,
            torre_numero,
            sentido,
            tipo_balancin,
            rango_oh_horas,
            TO_CHAR(inicio_oc, 'Mon-YY') as inicio_oc,
            horas_promedio_dia,
            factor_correccion,
            balancin_codigo,
            COUNT(*) as total_ohs,
            json_agg(
                json_build_object(
                    'numero', numero_oh,
                    'fecha', TO_CHAR(fecha_oh, 'Mon-YY'),
                    'anio', anio,
                    'horas', horas_operacion,
                    'backlog', backlog,
                    'dia', dia_semana
                ) ORDER BY numero_oh
            ) as todos_oh
        FROM app_historial_oh
    """
    
    if balancin_filtro:
        query += f" WHERE balancin_codigo = '{balancin_filtro}'"
    
    query += """
        GROUP BY 
            balancin_codigo,
            linea_nombre, 
            torre_numero, 
            sentido, 
            tipo_balancin, 
            rango_oh_horas,
            inicio_oc,
            horas_promedio_dia,
            factor_correccion
        ORDER BY linea_nombre, 
            CASE 
                WHEN torre_numero ~ '^[0-9]+$' THEN LPAD(torre_numero, 3, '0')
                ELSE LPAD(SUBSTRING(torre_numero FROM '^[0-9]+'), 3, '0') || SUBSTRING(torre_numero FROM '[A-Z]+$')
            END,
            sentido
    """
    
    with connection.cursor() as cursor:
        cursor.execute(query)
        columns = [col[0] for col in cursor.description]
        historial = []
        
        for row in cursor.fetchall():
            item = dict(zip(columns, row))
            
            todos_oh_str = item['todos_oh']
            if todos_oh_str:
                if isinstance(todos_oh_str, str):
                    todos_oh = json.loads(todos_oh_str)
                else:
                    todos_oh = todos_oh_str
            else:
                todos_oh = []
            
            item['todos_oh'] = todos_oh
            historial.append(item)
    
    # ===== APLICAR FILTROS ADICIONALES =====
    if linea_filtro:
        historial = [item for item in historial if item['linea_nombre'] == linea_filtro]
    if torre_filtro:
        historial = [item for item in historial if torre_filtro.lower() in item['torre_numero'].lower()]
    
    # ===== PARTE 3: CALCULAR ESTADOS =====
    total_normal = 0
    total_alerta = 0
    total_critico = 0
    total_sin_oh = 0
    
    for item in historial:
        if item['total_ohs'] == 0:
            estado = 'sin_oh'
            total_sin_oh += 1
        else:
            ultimo_oh = item['todos_oh'][-1] if item['todos_oh'] else None
            ultimo_backlog = ultimo_oh.get('backlog') if ultimo_oh else None
            
            if ultimo_backlog is None:
                estado = 'sin_oh'
                total_sin_oh += 1
            elif ultimo_backlog < 0:
                estado = 'critico'
                total_critico += 1
            elif ultimo_backlog < 5000:
                estado = 'alerta'
                total_alerta += 1
            else:
                estado = 'normal'
                total_normal += 1
        
        item['estado'] = estado
    
    if estado_filtro:
        historial = [item for item in historial if item['estado'] == estado_filtro]
    
    # ===== PARTE 4: DATOS PARA GRÁFICOS =====
    labels_lineas = []
    data_normal = []
    data_alerta = []
    data_critico = []
    
    for linea in lineas:
        count_normal = sum(1 for item in historial 
                          if item['linea_nombre'] == linea.nombre and item['estado'] == 'normal')
        count_alerta = sum(1 for item in historial 
                          if item['linea_nombre'] == linea.nombre and item['estado'] == 'alerta')
        count_critico = sum(1 for item in historial 
                           if item['linea_nombre'] == linea.nombre and item['estado'] == 'critico')
        
        if count_normal > 0 or count_alerta > 0 or count_critico > 0:
            labels_lineas.append(linea.nombre)
            data_normal.append(count_normal)
            data_alerta.append(count_alerta)
            data_critico.append(count_critico)
    
    torres_labels = []
    backlog_data = []
    backlog_colors = []
    
    for item in historial:
        sentido_short = "ASC" if item['sentido'] == 'ASCENDENTE' else "DES"
        etiqueta = f"{item['linea_nombre']} T{item['torre_numero']} {sentido_short}"
        torres_labels.append(etiqueta)
        
        ultimo_oh = item['todos_oh'][-1] if item['todos_oh'] else None
        ultimo_backlog = ultimo_oh.get('backlog') if ultimo_oh else None
        
        if ultimo_backlog is None:
            backlog_data.append(0)
            backlog_colors.append('#6c757d')
        else:
            backlog_data.append(ultimo_backlog)
            if ultimo_backlog < 0:
                backlog_colors.append('#dc3545')
            elif ultimo_backlog < 5000:
                backlog_colors.append('#ffc107')
            else:
                backlog_colors.append('#28a745')
    
    total_balancines = len(historial)
    total_oh = sum(item['total_ohs'] for item in historial)
    
    total_oh1 = sum(1 for item in historial for oh in item['todos_oh'] if oh['numero'] == 1)
    total_oh2 = sum(1 for item in historial for oh in item['todos_oh'] if oh['numero'] == 2)
    total_oh3 = sum(1 for item in historial for oh in item['todos_oh'] if oh['numero'] == 3)
    
    balancines_asc = sum(1 for item in historial if item['sentido'] == 'ASCENDENTE')
    balancines_desc = total_balancines - balancines_asc
    
    total_con_oh = total_normal + total_alerta + total_critico
    porcentaje_normal = (total_normal / total_con_oh * 100) if total_con_oh > 0 else 0
    porcentaje_alerta = (total_alerta / total_con_oh * 100) if total_con_oh > 0 else 0
    porcentaje_critico = (total_critico / total_con_oh * 100) if total_con_oh > 0 else 0
    
    context = {
        'lineas': lineas,
        'tipos': tipos,
        'linea_filtro': linea_filtro,
        'torre_filtro': torre_filtro,
        'estado_filtro': estado_filtro,
        'balancin_filtro': balancin_filtro,
        'historial': historial,
        'total_balancines': total_balancines,
        'balancines_asc': balancines_asc,
        'balancines_desc': balancines_desc,
        'total_oh': total_oh,
        'total_oh1': total_oh1,
        'total_oh2': total_oh2,
        'total_oh3': total_oh3,
        'total_normal': total_normal,
        'total_alerta': total_alerta,
        'total_critico': total_critico,
        'total_sin_oh': total_sin_oh,
        'porcentaje_normal': porcentaje_normal,
        'porcentaje_alerta': porcentaje_alerta,
        'porcentaje_critico': porcentaje_critico,
        'labels_lineas': json.dumps(labels_lineas),
        'data_normal': json.dumps(data_normal),
        'data_alerta': json.dumps(data_alerta),
        'data_critico': json.dumps(data_critico),
        'torres_labels': json.dumps(torres_labels),
        'backlog_data': json.dumps(backlog_data),
        'backlog_colors': json.dumps(backlog_colors),
    }
    
    return render(request, 'balancines/dashboard_oh_nuevo.html', context)


@login_required
def registrar_oh_balancin(request, codigo):
    """Registrar una nueva orden de horas para un balancín específico"""
    
    balancin = get_object_or_404(BalancinIndividual, codigo=codigo)
    
    if request.method == 'POST':
        form = RegistrarOHForm(request.POST)
        if form.is_valid():
            numero_oh = form.cleaned_data['numero_oh']
            fecha_oh = form.cleaned_data['fecha_oh']
            horas_operacion = form.cleaned_data['horas_operacion']
            observaciones = form.cleaned_data['observaciones']
            
            if HistorialOH.objects.filter(balancin=balancin, numero_oh=numero_oh).exists():
                messages.error(request, f'❌ Ya existe la OH #{numero_oh} para este balancín.')
            else:
                torre = balancin.torre
                linea_nombre = torre.linea.nombre if torre and torre.linea else 'N/A'
                
                if balancin.sentido == 'ASCENDENTE':
                    tipo = torre.tipo_balancin_ascendente if torre else 'Desconocido'
                else:
                    tipo = torre.tipo_balancin_descendente if torre else 'Desconocido'
                
                backlog = balancin.rango_horas_cambio_oh - horas_operacion
                
                nuevo_oh = HistorialOH.objects.create(
                    balancin=balancin,
                    linea_nombre=linea_nombre,
                    torre_numero=torre.numero_torre if torre else '0',
                    sentido=balancin.sentido,
                    tipo_balancin=tipo,
                    rango_oh_horas=balancin.rango_horas_cambio_oh,
                    inicio_oc='2014-05-01',
                    horas_promedio_dia=16,
                    factor_correccion=1.00,
                    numero_oh=numero_oh,
                    fecha_oh=fecha_oh,
                    horas_operacion=horas_operacion,
                    backlog=backlog,
                    anio=fecha_oh.year,
                    dia_semana=fecha_oh.strftime('%A'),
                    observaciones=observaciones,
                    usuario_registro=request.user.email if request.user.is_authenticated else 'Sistema'
                )
                
                messages.success(request, f'✅ OH #{numero_oh} registrado correctamente para {balancin.codigo}')
                return redirect('dashboard_oh_nuevo')
        else:
            messages.error(request, '❌ Por favor corrige los errores en el formulario.')
    else:
        ultimo_oh = HistorialOH.objects.filter(balancin=balancin).order_by('-numero_oh').first()
        siguiente_oh = (ultimo_oh.numero_oh + 1) if ultimo_oh else 1
        
        form = RegistrarOHForm(initial={
            'numero_oh': siguiente_oh,
            'fecha_oh': timezone.now().date()
        })
    
    context = {
        'form': form,
        'balancin': balancin,
        'title': f'Registrar OH para {balancin.codigo}'
    }
    
    return render(request, 'balancines/registrar_oh_balancin.html', context)

from django.shortcuts import render, get_object_or_404
from .models import BalancinIndividual, HistorialOH, Linea, Usuario
from .models import ConfiguracionRepuestosPorTipo, FormularioReacondicionamiento, ItemFormularioReacondicionamiento

def obtener_config_torque(tipo):
    configs = {
        # ===== SERIE T (501C) =====
        '4T-501C': {
            'poleas': 4,
            'segmentos_2p': 2,
            'segmentos_4p': 1,
            'seg_SE': 2,
            'consola': 2,
            'tiene_bastidor_6p': False,
            'lubricacion': {
                's2p': [1,2],
                's4p': [1,2],
                'cs': [1]
            },
            'lubricacion_extra': None
        },
        
        '6T-501C': {
            'poleas': 6,
            'segmentos_2p': 3,
            'segmentos_4p': 1,
            'seg_SE': 3,
            'consola': 2,
            'tiene_bastidor_6p': False,
            'lubricacion': {
                's2p': [1,2,3,4,5,6],
                's4p': [1,2],
                'cs': [1]
            },
            'lubricacion_extra': None
        },
        
        '8T-501C': {
            'poleas': 8,
            'segmentos_2p': 4,
            'segmentos_4p': 1,
            'seg_SE': 4,
            'consola': 2,
            'tiene_bastidor_6p': False,
            'lubricacion': {
                's2p': [1,2,3,4,5,6,7,8],
                's4p': [1,2,3,4],
                'cs': [1]
            },
            'lubricacion_extra': None
        },
        
        '10T-501C': {
            'poleas': 10,
            'segmentos_2p': 3,
            'segmentos_4p': 2,
            'seg_SE': 4,  # SE1, SE2, SE3, SE4
            'consola': 2,
            'tiene_bastidor_6p': True,
            'lubricacion': {
                's2p': [1,2,3,4,5],
                's4p': [1,2],
                'cs': [1]
            },
            'lubricacion_extra': {
                's4p_extra': [1,2],  # Segundo PL-S4P
                'etiqueta': 'Bastidor 6P',
                'posicion': 'despues_s4p'  # Va después del primer PL-S4P
            }
        },
        
        '12T-501C': {
            'poleas': 12,
            'segmentos_2p': 3,
            'segmentos_4p': 2,
            'seg_SE': 4,  # SE1, SE2, SE3, SE4
            'consola': 2,
            'tiene_bastidor_6p': True,
            'lubricacion': {
                's2p': [1,2,3,4,5,6],
                's4p': [1,2],
                'cs': [1]
            },
            'lubricacion_extra': {
                's4p_extra': [1,2],  # Segundo PL-S4P
                'etiqueta': 'Bastidor 6P',
                'posicion': 'despues_s4p'
            }
        },
        
        # ===== SERIE N/4TR (420C) =====
        '8N/4TR-420C': {
            'poleas': 16,
            'segmentos_2p': 4,
            'segmentos_4p': 2,
            'seg_SE': 4,
            'consola': 2,
            'tiene_bastidor_6p': False,
            'lubricacion': {
                's2p': [1,2,3,4,5,6,7,8],
                's4p': [1,2,3,4],
                'cs': [1]
            },
            'lubricacion_extra': None
        },
        
        '10N/4TR-420C': {
            'poleas': 16,
            'segmentos_2p': 4,
            'segmentos_4p': 8,
            'seg_SE': 4,
            'consola': 2,
            'tiene_bastidor_6p': False,
            'lubricacion': {
                's2p': [1,2,3,4,5,6,7,8],
                's4p': [1,2,3,4],
                'cs': [1]
            },
            'lubricacion_extra': None
        },
        
        '12N/4TR-420C': {
            'poleas': 16,
            'segmentos_2p': 4,
            'segmentos_4p': 2,
            'seg_SE': 4,
            'consola': 2,
            'tiene_bastidor_6p': False,
            'lubricacion': {
                's2p': [1,2,3,4,5,6,7,8],
                's4p': [1,2,3,4],
                'cs': [1]
            },
            'lubricacion_extra': None
        },
        
        '14N/4TR-420C': {
            'poleas': 16,
            'segmentos_2p': 4,
            'segmentos_4p': 2,
            'seg_SE': 4,
            'consola': 2,
            'tiene_bastidor_6p': False,
            'lubricacion': {
                's2p': [1,2,3,4,5,6,7,8],
                's4p': [1,2,3,4],
                'cs': [1]
            },
            'lubricacion_extra': None
        },
        
        '16N/4TR-420C': {
            'poleas': 16,
            'segmentos_2p': 4,
            'segmentos_4p': 4,
            'seg_SE': 4,
            'consola': 2,
            'tiene_bastidor_6p': False,
            'lubricacion': {
                's2p': [1,2,3,4,5,6,7,8],
                's4p': [1,2,3,4],
                'cs': [1]
            },
            'lubricacion_extra': None
        },
        
        # ===== HÍBRIDOS =====
        '4T/4N-420C': {
            'poleas': 8,
            'segmentos_2p': 4,
            'segmentos_4p': 2,
            'seg_SE': 4,
            'consola': 2,
            'tiene_bastidor_6p': False,
            'lubricacion': {
                's2p': [1,2,3,4,5,6,7,8],
                's4p': [1,2,3,4],
                'cs': [1]
            },
            'lubricacion_extra': None
        },
        
        '8T/8N-420C': {
            'poleas': 8,
            'segmentos_2p': 4,
            'segmentos_4p': 2,
            'seg_SE': 4,
            'consola': 2,
            'tiene_bastidor_6p': False,
            'lubricacion': {
                's2p': [1,2,3,4,5,6,7,8],
                's4p': [1,2,3,4],
                'cs': [1]
            },
            'lubricacion_extra': None
        },
    }
    return configs.get(tipo, configs['4T-501C'])


@login_required
def crear_formulario_control(request, codigo):
    """
    Vista para crear formulario de control de reacondicionamiento
    """
    import sys
    from django.db import transaction, models
    from collections import OrderedDict, defaultdict
    from django.utils import timezone
    
    # Obtener el balancín
    balancin = get_object_or_404(BalancinIndividual, codigo=codigo)
    
    # Obtener el último OH
    ultimo_oh = HistorialOH.objects.filter(balancin=balancin).order_by('-numero_oh').first()
    
    # Obtener el tipo de balancín
    tipo_codigo = balancin.tipo_balancin_codigo
    
    # ===== API PARA CARGAR TORRES CON AMBOS SENTIDOS =====
    if request.headers.get('X-Requested-With') == 'XMLHttpRequest' and request.GET.get('linea'):
        from django.http import JsonResponse
        linea_nombre = request.GET.get('linea')
        tipo_balancin = request.GET.get('tipo')
        
        try:
            linea = Linea.objects.get(nombre=linea_nombre)
            # Buscar torres que tengan este tipo de balancín
            torres = Torre.objects.filter(
                linea=linea
            ).filter(
                models.Q(tipo_balancin_ascendente=tipo_balancin) |
                models.Q(tipo_balancin_descendente=tipo_balancin)
            ).select_related('seccion').order_by('numero_torre')
            
            torres_data = []
            for t in torres:
                # Verificar sentido ascendente
                if t.tipo_balancin_ascendente == tipo_balancin:
                    torres_data.append({
                        'id': f"{t.id}_ASC",
                        'numero': t.numero_torre,
                        'sentido': 'ASCENDENTE',
                        'texto': f"Torre {t.numero_torre} / ASC"
                    })
                
                # Verificar sentido descendente
                if t.tipo_balancin_descendente == tipo_balancin:
                    torres_data.append({
                        'id': f"{t.id}_DESC",
                        'numero': t.numero_torre,
                        'sentido': 'DESCENDENTE',
                        'texto': f"Torre {t.numero_torre} / DESC"
                    })
            
            return JsonResponse({'torres': torres_data})
        except Linea.DoesNotExist:
            return JsonResponse({'torres': []})
    
    # ===== PROCESAR POST (GUARDAR) =====
    if request.method == 'POST':
        print("=" * 50)
        print("DATOS RECIBIDOS DEL FORMULARIO:")
        for key, value in request.POST.items():
            print(f"  {key}: {value}")
        print("=" * 50)
        sys.stdout.flush()
        
        # Generar código de formulario
        codigo_formulario = generar_codigo_formulario(tipo_codigo)
        
        # Usar transacción para asegurar integridad
        with transaction.atomic():
            # Crear el formulario
            formulario = FormularioReacondicionamiento.objects.create(
                codigo_formulario=codigo_formulario,
                tipo=tipo_codigo,
                balancin=balancin,
                historial_oh=ultimo_oh,
                fecha=request.POST.get('fecha', timezone.now().date()),
                horas_funcionamiento=request.POST.get('horas_funcionamiento', 0),
                linea_inicial=request.POST.get('linea_inicial', ''),
                torre_inicial=request.POST.get('torre_inicial', ''),
                linea_final=request.POST.get('linea_final', ''),
                torre_final=request.POST.get('torre_final', ''),
                sentido_final=request.POST.get('sentido_final', ''),
                control_particulas=request.POST.get('control_particulas') == 'on',
                codigo_informe=request.POST.get('codigo_informe', ''),
                torque_verificado=request.POST.get('torque_verificado') == 'on',
                limpieza_verificada=request.POST.get('limpieza_verificada') == 'on',
                continuidad_verificada=request.POST.get('continuidad_verificada') == 'on',
                realizado_por_analisis_id=request.POST.get('realizado_analisis'),
                aprobado_por_id=request.POST.get('jefe_id'),
                usuario_creacion=request.user if request.user.is_authenticated else None
            )
            
            # ===== PROCESAR TÉCNICOS DE LA TABLA REALIZADO =====
            tecnicos_procesados = 0
            total_filas = int(request.POST.get('total_filas_realizado', 0))
            
            for i in range(total_filas):
                usuario_id = request.POST.get(f'usuario_realizado_{i}')
                if usuario_id and usuario_id.strip():
                    firma = request.POST.get(f'firma_realizado_{i}', '')
                    
                    # Guardar en la tabla TecnicoFormulario
                    TecnicoFormulario.objects.create(
                        formulario=formulario,
                        usuario_id=usuario_id,
                        firma=firma
                    )
                    
                    # Guardar el primer técnico como realizado_por_recambio
                    if tecnicos_procesados == 0:
                        formulario.realizado_por_recambio_id = usuario_id
                        formulario.save()
                        print(f"  👤 Técnico principal: ID {usuario_id}")
                    
                    tecnicos_procesados += 1
                    print(f"  👤 Técnico {tecnicos_procesados}: ID {usuario_id}, Firma: {firma}")
            
            # ===== PROCESAR REPUESTOS CONFIGURADOS (con radios SI/NO) =====
            items_procesados = 0
            for key, value in request.POST.items():
                if key.startswith('recambio_'):
                    item_id = key.replace('recambio_', '')
                    print(f"🔍 Encontrado recambio para item_id: {item_id}, valor: {value}")
                    
                    reemplazado = value == 'SI'
                    
                    if reemplazado:
                        cantidad_key = f'cantidad_{item_id}'
                        cantidad = int(request.POST.get(cantidad_key, 0))
                        
                        if cantidad > 0:
                            try:
                                config = ConfiguracionRepuestosPorTipo.objects.select_related('repuesto').get(id=item_id)
                                
                                if not config.repuesto:
                                    print(f"  ❌ ERROR: La configuración {item_id} no tiene repuesto asociado")
                                    continue
                                
                                repuesto = config.repuesto
                                stock_antes = repuesto.cantidad
                                
                                # Verificar stock suficiente
                                if repuesto.cantidad < cantidad:
                                    print(f"  ❌ Stock insuficiente: disponible {repuesto.cantidad}, requerido {cantidad}")
                                    messages.warning(request, f'Stock insuficiente para {config.id_original}')
                                    continue
                                
                                # Descontar stock
                                repuesto.cantidad -= cantidad
                                repuesto.fecha_ultimo_movimiento = timezone.now()
                                repuesto.fecha_ultima_salida = timezone.now()
                                repuesto.save()
                                
                                # Registrar en historial
                                HistorialRepuesto.objects.create(
                                    repuesto=repuesto,
                                    tipo_movimiento='salida',
                                    cantidad=cantidad,
                                    stock_restante=repuesto.cantidad,
                                    observaciones=f"Salida por formulario {codigo_formulario}"
                                )
                                
                                # Crear el item del formulario
                                ItemFormularioReacondicionamiento.objects.create(
                                    formulario=formulario,
                                    configuracion=config,
                                    repuesto=repuesto,
                                    id_original=config.id_original,
                                    descripcion=config.descripcion,
                                    cantidad_requerida=config.cantidad_por_balancin,
                                    cantidad_usada=cantidad,
                                    fue_reemplazado=True,
                                    stock_antes=stock_antes,
                                    stock_despues=repuesto.cantidad
                                )
                                items_procesados += 1
                                print(f"  ✅ Item creado: {config.id_original}")
                                
                            except Exception as e:
                                print(f"  ❌ ERROR: {str(e)}")
            
            # ===== PROCESAR REPUESTOS DE "OTRAS PIEZAS REEMPLAZADAS" (CORREGIDO) =====
            items_procesados_otros = 0
            total_filas_otros = int(request.POST.get('total_filas_otros', 0))
            print(f"🔍 Procesando {total_filas_otros} filas de otras piezas")
            
            for i in range(total_filas_otros):
                item_id = request.POST.get(f'otro_id_{i}', '')
                if not item_id or item_id.strip() == '':
                    continue
                
                descripcion = request.POST.get(f'otro_desc_{i}', '')
                cantidad = int(request.POST.get(f'otro_cant_{i}', 0))
                cantidad_total = int(request.POST.get(f'otro_total_{i}', 0))
                observaciones = request.POST.get(f'otro_obs_{i}', '')
                origen = request.POST.get(f'otro_origen_{i}', 'balancin')  # 🔥 LEER EL ORIGEN
                
                print(f"  📦 Procesando otro repuesto: {item_id} - {descripcion} - Origen: {origen} - Cantidad: {cantidad}")
                
                if cantidad <= 0:
                    print(f"  ⚠️ Cantidad inválida: {cantidad}, se omite")
                    continue
                
                # 🔥 BUSCAR SOLO EN LA TABLA CORRESPONDIENTE SEGÚN EL ORIGEN
                repuesto_encontrado = None
                
                if origen == 'balancin':
                    try:
                        repuesto_encontrado = RepuestoBalancin.objects.get(item=item_id)
                        print(f"  ✅ Repuesto encontrado en balancines: {repuesto_encontrado.item}")
                    except RepuestoBalancin.DoesNotExist:
                        print(f"  ❌ Repuesto de balancín no encontrado: {item_id}")
                        messages.warning(request, f'Repuesto de balancín no encontrado: {item_id} - {descripcion}')
                        continue
                
                elif origen == 'adicional':
                    try:
                        repuesto_encontrado = RepuestoAdicional.objects.get(item=item_id)
                        print(f"  ✅ Repuesto encontrado en adicionales: {repuesto_encontrado.item}")
                    except RepuestoAdicional.DoesNotExist:
                        print(f"  ❌ Repuesto adicional no encontrado: {item_id}")
                        messages.warning(request, f'Repuesto adicional no encontrado: {item_id} - {descripcion}')
                        continue
                
                else:
                    print(f"  ❌ Origen desconocido: {origen}")
                    continue
                
                # Verificar stock suficiente
                if repuesto_encontrado.cantidad < cantidad:
                    print(f"  ❌ Stock insuficiente: disponible {repuesto_encontrado.cantidad}, requerido {cantidad}")
                    messages.warning(request, f'Stock insuficiente para {item_id} - {descripcion}')
                    continue
                
                # Guardar stock antes
                stock_antes = repuesto_encontrado.cantidad
                
                # Descontar stock
                repuesto_encontrado.cantidad -= cantidad
                repuesto_encontrado.fecha_ultimo_movimiento = timezone.now()
                repuesto_encontrado.fecha_ultima_salida = timezone.now()
                repuesto_encontrado.save()
                
                # Registrar en historial según el origen
                if origen == 'balancin':
                    HistorialRepuesto.objects.create(
                        repuesto=repuesto_encontrado,
                        tipo_movimiento='salida',
                        cantidad=cantidad,
                        stock_restante=repuesto_encontrado.cantidad,
                        observaciones=f"Salida por formulario {codigo_formulario} (otras piezas: {descripcion})"
                    )
                else:  # origen == 'adicional'
                    HistorialAdicional.objects.create(
                        repuesto=repuesto_encontrado,
                        tipo_movimiento='salida',
                        cantidad=cantidad,
                        stock_restante=repuesto_encontrado.cantidad,
                        observaciones=f"Salida por formulario {codigo_formulario} (otras piezas: {descripcion})",
                        usuario=request.user if request.user.is_authenticated else None
                    )
                
                items_procesados += 1
                items_procesados_otros += 1
                print(f"  ✅ Otro repuesto procesado: {item_id} - Stock: {stock_antes} → {repuesto_encontrado.cantidad}")
        
        print(f"🎯 TOTAL: {items_procesados} repuestos, {tecnicos_procesados} técnicos")
        messages.success(request, f'✅ Formulario {codigo_formulario} guardado correctamente. {items_procesados} repuestos procesados.')
        return redirect('dashboard_oh_nuevo')
    
    # ===== CÓDIGO PARA GET (mostrar formulario) =====
    
    # Filtrar líneas que tienen torres con este tipo de balancín
    lineas_disponibles = Linea.objects.filter(
        models.Q(torres__tipo_balancin_ascendente=tipo_codigo) |
        models.Q(torres__tipo_balancin_descendente=tipo_codigo)
    ).distinct().order_by('nombre')
    
    usuarios_tecnicos = Usuario.objects.filter(rol__in=['tecnico', 'supervisor']).order_by('nombre')
    jefes = Usuario.objects.filter(rol='jefe').order_by('nombre')
    
    # Datos del balancín
    torre = balancin.torre
    linea_actual = torre.linea.nombre if torre and torre.linea else 'N/A'
    torre_actual = torre.numero_torre if torre else 'N/A'
    horas_actuales = ultimo_oh.horas_operacion if ultimo_oh else 0
    
    # ===== OBTENER REPUESTOS CONFIGURADOS =====
    config_repuestos = ConfiguracionRepuestosPorTipo.objects.filter(
        tipo_balancin__codigo=tipo_codigo
    ).select_related('repuesto').order_by('grupo', 'orden')
    
    print(f"Procesando {config_repuestos.count()} repuestos para {tipo_codigo}")
    
    # ===== LÓGICA ESPECIAL PARA 14N/4TR-420C (LISTA PLANA SIN GRUPOS) =====
    if tipo_codigo == '14N/4TR-420C':
        print("🔧 Tipo 14N/4TR-420C detectado - Mostrando como lista plana")
        
        # Crear lista de items sueltos
        items_sueltos = []
        
        for config in config_repuestos:
            items_sueltos.append({
                'id': config.id,
                'id_original': config.id_original,
                'descripcion': config.descripcion,
                'es_conjunto': False,
                'cantidad': config.cantidad_por_balancin,
                'cantidad_total': config.cantidad_total,
                'orden': config.orden
            })
            print(f"  Item agregado: {config.id_original} - {config.descripcion[:30]}")
        
        # Ordenar por orden
        items_sueltos.sort(key=lambda x: x['orden'])
        
        print(f"Total items procesados: {len(items_sueltos)}")
        
        # Crear diccionario con un grupo vacío
        repuestos_agrupados = OrderedDict()
        repuestos_agrupados[''] = items_sueltos  # Grupo sin nombre
        
    else:
        # ===== LÓGICA NORMAL PARA OTROS TIPOS (con grupos y conjuntos) =====
        
        # PASO 1: Identificar TODOS los conjuntos (es_conjunto=True)
        conjuntos = {}
        items_sueltos = defaultdict(list)
        componentes_asignados = set()
        
        print("PASO 1: Identificando conjuntos...")
        for config in config_repuestos:
            if config.es_conjunto:
                conjuntos[config.id_original] = {
                    'id': config.id,
                    'id_original': config.id_original,
                    'descripcion': config.descripcion,
                    'grupo': config.grupo,
                    'es_conjunto': True,
                    'componentes': [],
                    'orden': config.orden
                }
                print(f"  Conjunto encontrado: {config.id_original} - {config.descripcion[:30]}...")
        
        # PASO 2: Identificar componentes y asignarlos a sus conjuntos
        print("PASO 2: Asignando componentes a conjuntos...")
        for config in config_repuestos:
            if not config.es_conjunto:
                if config.conjunto_padre_id and config.conjunto_padre_id in conjuntos:
                    # Es componente de un conjunto
                    conjuntos[config.conjunto_padre_id]['componentes'].append({
                        'id': config.id,
                        'id_original': config.id_original,
                        'descripcion': config.descripcion,
                        'cantidad': config.cantidad_por_balancin,
                        'cantidad_total': config.cantidad_total,
                        'orden': config.orden
                    })
                    componentes_asignados.add(config.id)
                    print(f"  Componente {config.id_original} asignado a conjunto {config.conjunto_padre_id}")
                else:
                    # Es item suelto (sin conjunto padre)
                    items_sueltos[config.grupo].append({
                        'id': config.id,
                        'id_original': config.id_original,
                        'descripcion': config.descripcion,
                        'es_conjunto': False,
                        'cantidad': config.cantidad_por_balancin,
                        'cantidad_total': config.cantidad_total,
                        'orden': config.orden
                    })
                    print(f"  Item suelto: {config.id_original} en grupo {config.grupo}")
    
        # PASO 3: Orden de grupos según el tipo de balancín
        if tipo_codigo in ['4T-501C', '6T-501C', '8T-501C', '10T-501C', '12T-501C']:
            orden_grupos = ['POLEAS', 'SEGMENTOS_2P', 'SEGMENTOS_4P', 'CONJUNTOS', 'OTROS']
    
        elif tipo_codigo in ['8N/4TR-420C', '10N/4TR-420C', '14N/4TR-420C']:
            orden_grupos = ['POLEAS', 'SEGMENTOS_2N', 'SEGMENTOS_4N', 'SEGMENTOS_4N/TR', 'CONJUNTOS', 'OTROS']
    
        elif tipo_codigo == '16N/4TR-420C':
            orden_grupos = ['POLEAS', 'SEGMENTOS_2S', 'SEGMENTOS_2P', 'CONJUNTOS_4P4S', 'OTROS']
    
        elif tipo_codigo == '12N/4TR-420C':
            orden_grupos = ['POLEAS', 'POLEAS_SENSOR', 'SEGMENTOS_2S', 'SEGMENTOS_4N/TR', 'SEGMENTOS_4N/TR_2', 'CONJUNTOS', 'OTROS']
    
        elif tipo_codigo in ['4T/4N-420C', '8T/8N-420C']:
            orden_grupos = ['POLEAS', 'SEGMENTOS', 'SEGMENTOS_2S', 'SEGMENTOS_2P', 'SEGMENTOS_2N', 'SEGMENTOS_4N', 'CONJUNTOS', 'OTROS']
    
        else:
            orden_grupos = ['POLEAS', 'SEGMENTOS', 'CONJUNTOS', 'OTROS']
        
        repuestos_agrupados = OrderedDict()
        
        # Inicializar todos los grupos
        for grupo in orden_grupos:
            repuestos_agrupados[grupo] = []
        
        # PASO 4: Agregar conjuntos a sus grupos
        print("PASO 4: Agregando conjuntos a grupos...")
        for conjunto in conjuntos.values():
            grupo = conjunto['grupo']
            if grupo in repuestos_agrupados:
                conjunto['componentes'].sort(key=lambda x: x['orden'])
                repuestos_agrupados[grupo].append(conjunto)
                print(f"  Conjunto {conjunto['id_original']} agregado a grupo {grupo} con {len(conjunto['componentes'])} componentes")
        
        # PASO 5: Agregar items sueltos a sus grupos
        print("PASO 5: Agregando items sueltos...")
        for grupo, items in items_sueltos.items():
            if grupo in repuestos_agrupados:
                items.sort(key=lambda x: x['orden'])
                repuestos_agrupados[grupo].extend(items)
                print(f"  {len(items)} items sueltos agregados a grupo {grupo}")
        
        # PASO 6: Eliminar grupos vacíos
        repuestos_agrupados = OrderedDict([
            (grupo, items) for grupo, items in repuestos_agrupados.items() if items
        ])
    
    # ===== CONTEXTO PARA EL TEMPLATE =====
    context = {
        'balancin': balancin,
        'tipo_balancin': tipo_codigo,
        'linea_actual': linea_actual,
        'torre_actual': torre_actual,
        'sentido': balancin.sentido,
        'horas_actuales': horas_actuales,
        'ultimo_oh': ultimo_oh,
        'lineas_disponibles': lineas_disponibles,
        'usuarios_tecnicos': usuarios_tecnicos,
        'jefes': jefes,
        'repuestos_agrupados': repuestos_agrupados,
        'total_repuestos': config_repuestos.count(),
        'config': obtener_config_torque(tipo_codigo),
    }
    
    # Renderizar el template específico para este tipo
    template_name = f'balancines/formularios/formulario_{tipo_codigo.replace("/", "-")}.html'
    return render(request, template_name, context)


@login_required
def torres_por_linea_api(request):
    """API para obtener torres de una línea que tienen un tipo específico de balancín"""
    from django.http import JsonResponse
    
    linea_nombre = request.GET.get('linea')
    tipo_balancin = request.GET.get('tipo')
    
    if not linea_nombre or not tipo_balancin:
        return JsonResponse({'torres': []})
    
    try:
        linea = Linea.objects.get(nombre=linea_nombre)
        torres = Torre.objects.filter(
            linea=linea
        ).filter(
            models.Q(tipo_balancin_ascendente=tipo_balancin) |
            models.Q(tipo_balancin_descendente=tipo_balancin)
        ).select_related('seccion').order_by('numero_torre')
        
        torres_data = [{
            'id': t.id,
            'numero': t.numero_torre,
            'texto': f"Torre {t.numero_torre} ({t.seccion.nombre})"
        } for t in torres]
        
        return JsonResponse({'torres': torres_data})
    except Linea.DoesNotExist:
        return JsonResponse({'torres': []})

def generar_codigo_formulario(tipo):
    """
    Genera un código de formulario automático
    Ej: TRM-FCRB-4T-501C-001
    """
    from django.db.models import Max
    
    # Limpiar el tipo para el código (reemplazar / por -)
    tipo_limpio = tipo.replace('/', '-')
    
    # Buscar el último número
    ultimo = FormularioReacondicionamiento.objects.filter(
        codigo_formulario__startswith=f"TRM-FCRB-{tipo_limpio}-"
    ).aggregate(Max('codigo_formulario'))['codigo_formulario__max']
    
    if ultimo:
        # Extraer el número (ej: 001)
        try:
            numero = int(ultimo.split('-')[-1]) + 1
        except:
            numero = 1
    else:
        numero = 1
    
    return f"TRM-FCRB-{tipo_limpio}-{numero:03d}"

@login_required
def lista_formularios(request):
    """
    Lista todos los formularios de reacondicionamiento guardados
    """
    formularios = FormularioReacondicionamiento.objects.all().select_related(
        'balancin', 'balancin__torre__linea', 'balancin__torre__seccion',
        'historial_oh', 'realizado_por_analisis', 'realizado_por_recambio', 
        'aprobado_por'
    ).prefetch_related(
        'tecnicos',  # Para cargar todos los técnicos
        'tecnicos__usuario'
    ).order_by('-fecha_creacion')
    
    # Estadísticas
    total_formularios = formularios.count()
    total_repuestos_usados = ItemFormularioReacondicionamiento.objects.filter(
        fue_reemplazado=True
    ).aggregate(total=Sum('cantidad_usada'))['total'] or 0
    
    context = {
        'formularios': formularios,
        'total_formularios': total_formularios,
        'total_repuestos_usados': total_repuestos_usados,
    }
    return render(request, 'balancines/lista_formularios.html', context)

@login_required
def detalle_formulario(request, codigo):
    """
    Detalle de un formulario específico
    """
    formulario = get_object_or_404(
        FormularioReacondicionamiento.objects.select_related(
            'balancin', 'historial_oh', 'realizado_por_analisis', 
            'realizado_por_recambio', 'aprobado_por', 'usuario_creacion'
        ).prefetch_related('items__repuesto'),
        codigo_formulario=codigo
    )
    
    items_usados = formulario.items.filter(fue_reemplazado=True)
    total_items = formulario.items.count()
    
    context = {
        'formulario': formulario,
        'items_usados': items_usados,
        'total_items': total_items,
    }
    return render(request, 'balancines/detalle_formulario.html', context)



from django.http import JsonResponse
from django.db.models import Q

@login_required
def buscar_repuestos_api(request):
    """API para buscar repuestos en ambas tablas"""
    query = request.GET.get('q', '').strip()
    
    if len(query) < 2:
        return JsonResponse({'results': []})
    
    resultados = []
    query_upper = query.upper()
    
    # Buscar en RepuestoBalancin
    repuestos_balancin = RepuestoBalancin.objects.filter(
        Q(item__icontains=query_upper) | 
        Q(descripcion__icontains=query)
    )[:10]
    
    for r in repuestos_balancin:
        resultados.append({
            'id': r.item,
            'item': r.item,
            'descripcion': r.descripcion,
            'tipo': 'Balancín',
            'cantidad': r.cantidad,
            'origen': 'balancin'
        })
    
    # Buscar en RepuestoAdicional
    repuestos_adicionales = RepuestoAdicional.objects.filter(
        Q(item__icontains=query_upper) | 
        Q(descripcion__icontains=query)
    )[:10]
    
    for r in repuestos_adicionales:
        resultados.append({
            'id': r.item,
            'item': r.item,
            'descripcion': r.descripcion,
            'tipo': 'Adicional',
            'cantidad': r.cantidad,
            'origen': 'adicional'
        })
    
    # Ordenar por item
    resultados = sorted(resultados, key=lambda x: x['item'])[:15]
    
    return JsonResponse({'results': resultados})


from django.http import JsonResponse
from .models import Usuario

@login_required
def buscar_usuarios_api(request):
    """API para buscar usuarios por nombre o email"""
    query = request.GET.get('q', '').strip()
    
    if len(query) < 2:
        return JsonResponse({'results': []})
    
    usuarios = Usuario.objects.filter(
        Q(nombre__icontains=query) | 
        Q(email__icontains=query)
    )[:10]
    
    results = []
    for user in usuarios:
        results.append({
            'id': user.id,
            'nombre': user.nombre,
            'email': user.email,
            'rol': user.get_rol_display(),  # Esto muestra "Jefe", "Supervisor", "Técnico"
            'rol_value': user.rol  # Esto guarda 'jefe', 'supervisor', 'tecnico'
        })
    
    return JsonResponse({'results': results})


@login_required
def buscar_jefes_api(request):
    """API para buscar solo usuarios con rol de jefe"""
    query = request.GET.get('q', '').strip()
    
    usuarios = Usuario.objects.filter(rol='jefe')
    
    if len(query) >= 2:
        usuarios = usuarios.filter(
            Q(nombre__icontains=query) | 
            Q(email__icontains=query)
        )
    
    usuarios = usuarios[:10]
    
    results = []
    for user in usuarios:
        results.append({
            'id': user.id,
            'nombre': user.nombre,
            'email': user.email,
            'rol': user.get_rol_display(),
        })
    
    return JsonResponse({'results': results})

from django.shortcuts import render, get_object_or_404
from django.contrib.auth.decorators import login_required
from .models import Torre, BalancinIndividual, HistorialOH, Linea, TipoBalancin
from django.conf import settings




@login_required
def historial_torre_con_filtros(request):
    """
    Vista con filtros para buscar torres por línea, número y tipo de balancín
    """
    # Obtener todas las líneas para el filtro
    lineas = Linea.objects.all()
    
    # Obtener todos los tipos de balancín para el filtro
    tipos_balancin = TipoBalancin.objects.all().values_list('codigo', flat=True)
    
    # Inicializar variables
    torre_seleccionada = None
    balancines_data = []
    total_oh_torre = 0
    ultimo_oh_torre = None
    torres_linea = []
    linea_seleccionada = None
    torres_duplicadas = []
    
    # Procesar filtros si vienen del formulario
    linea_id = request.GET.get('linea')
    numero_torre = request.GET.get('numero_torre')
    tipo_balancin = request.GET.get('tipo_balancin')
    seccion_id = request.GET.get('seccion_id')
    
    # 🔹 Si hay línea seleccionada, obtener todas sus torres (ordenadas)
    if linea_id:
        try:
            linea_seleccionada = Linea.objects.get(id=linea_id)
            # Obtener todas las torres de la línea
            torres_query = Torre.objects.filter(
                linea_id=linea_id
            ).select_related('linea', 'seccion')
            
            # Ordenar numéricamente (maneja texto y números)
            torres_linea = sorted(
                torres_query, 
                key=lambda t: (
                    int(t.numero_torre) if t.numero_torre.isdigit() else float('inf'),
                    t.numero_torre
                )
            )
            
        except Linea.DoesNotExist:
            pass
    
    # 🔹 Si hay torre seleccionada, mostrar su detalle (manejando duplicados)
    if linea_id and numero_torre:
        # Buscar todas las torres que coincidan con línea y número
        torres_coincidentes = Torre.objects.select_related('linea', 'seccion').filter(
            linea_id=linea_id,
            numero_torre=numero_torre
        )
        
        if torres_coincidentes.count() > 1:
            # Si hay múltiples torres con el mismo número
            if seccion_id:
                # Si se especificó una sección, buscar esa torre específica
                try:
                    torre_seleccionada = torres_coincidentes.get(seccion_id=seccion_id)
                except Torre.DoesNotExist:
                    torres_duplicadas = torres_coincidentes
            else:
                # Si no se especificó sección, mostrar todas para que el usuario elija
                torres_duplicadas = torres_coincidentes
        elif torres_coincidentes.count() == 1:
            # Si hay una sola torre, seleccionarla directamente
            torre_seleccionada = torres_coincidentes.first()
        
        # Si hay una torre seleccionada (única o específica), mostrar sus balancines
        if torre_seleccionada:
            # Obtener los balancines de esta torre
            balancines = BalancinIndividual.objects.filter(
                torre=torre_seleccionada
            ).order_by('sentido')
            
            # Preparar datos de balancines
            for balancin in balancines:
                # Determinar el tipo de balancín según el sentido
                if balancin.sentido == 'ASCENDENTE':
                    tipo_codigo = torre_seleccionada.tipo_balancin_ascendente
                else:
                    tipo_codigo = torre_seleccionada.tipo_balancin_descendente
                
                # Si hay filtro por tipo, saltar si no coincide
                if tipo_balancin and tipo_codigo != tipo_balancin:
                    continue
                
                # Obtener historial de OH
                historial = HistorialOH.objects.filter(
                    balancin=balancin
                ).order_by('-fecha_oh')
                
                balancin_dict = {
                    'objeto': balancin,
                    'codigo': balancin.codigo,
                    'sentido': balancin.sentido,
                    'sentido_display': balancin.get_sentido_display(),
                    'rango_horas_cambio_oh': balancin.rango_horas_cambio_oh,
                    'observaciones': balancin.observaciones,
                    'fecha_registro': balancin.fecha_registro,
                    'tipo_codigo': tipo_codigo,
                    'oh_historial': historial,
                    'total_oh': historial.count(),
                    'ultimo_oh': historial.first() if historial.exists() else None
                }
                
                balancines_data.append(balancin_dict)
                
                # Actualizar estadísticas
                if historial.exists():
                    total_oh_torre += balancin_dict['total_oh']
                    if not ultimo_oh_torre or historial.first().fecha_oh > ultimo_oh_torre.fecha_oh:
                        ultimo_oh_torre = historial.first()
    
    context = {
        'lineas': lineas,
        'tipos_balancin': tipos_balancin,
        'torre': torre_seleccionada,
        'balancines': balancines_data,
        'total_oh_torre': total_oh_torre,
        'ultimo_oh_torre': ultimo_oh_torre,
        'total_balancines': len(balancines_data),
        'filtros': {
            'linea': linea_id,
            'numero_torre': numero_torre,
            'tipo_balancin': tipo_balancin,
            'seccion_id': seccion_id,
        },
        'torres_linea': torres_linea,
        'linea_seleccionada': linea_seleccionada,
        'torres_duplicadas': torres_duplicadas,
        'MEDIA_URL': settings.MEDIA_URL,
    }
    
    return render(request, 'balancines/historial_torre.html', context)

from django.core.paginator import Paginator



@login_required
def historial_balancin(request, codigo):
    """
    Muestra el historial completo de un balancín específico - VERSIÓN OPTIMIZADA
    """
    from django.core.paginator import Paginator
    from django.db import models
    
    # Obtener el balancín con TODOS los datos relacionados en UNA SOLA CONSULTA
    balancin = get_object_or_404(
        BalancinIndividual.objects.select_related(
            'torre__linea',  # Torre y su línea en una sola consulta
            'torre__seccion'
        ),
        codigo=codigo
    )
    
    # Obtener tipo de balancín directamente desde el balancín (es propiedad)
    tipo_balancin_codigo = balancin.tipo_balancin_codigo
    
    # Obtener historial de OH con consulta optimizada
    historial_oh = HistorialOH.objects.filter(
        balancin=balancin
    ).only(  # Solo cargar los campos que necesitamos
        'numero_oh', 
        'fecha_oh', 
        'horas_operacion', 
        'backlog', 
        'observaciones'
    ).order_by('-fecha_oh', '-numero_oh')
    
    # Contar rápido sin cargar todos los objetos
    total_oh = historial_oh.count()
    
    # Obtener último OH de manera eficiente
    ultimo_oh = historial_oh.first()
    
    # Paginación
    per_page = request.GET.get('per_page', 10)
    try:
        per_page = int(per_page)
    except ValueError:
        per_page = 10
    
    paginator = Paginator(historial_oh, per_page)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    # Datos para gráficos (solo si hay datos)
    fechas = []
    backlogs = []
    if total_oh > 0:
        # Obtener solo los últimos 10 para el gráfico
        ultimos_10 = historial_oh[:10]
        fechas = [h.fecha_oh.strftime('%d/%m/%Y') for h in ultimos_10]
        backlogs = [h.backlog or 0 for h in ultimos_10]
    
    context = {
        'balancin': balancin,
        'page_obj': page_obj,
        'total_oh': total_oh,
        'ultimo_oh': ultimo_oh,
        'fechas': fechas,
        'backlogs': backlogs,
        'tipo_balancin': tipo_balancin_codigo,
        # Indicador para el template de si hay datos o no
        'hay_datos': total_oh > 0,
    }
    
    return render(request, 'balancines/historial_balancin.html', context)   


from django.utils.dateparse import parse_date
from django.db.models import Count, Sum, Q
from datetime import timedelta
import calendar
@login_required
def api_historial_repuestos_balancin_filtros(request):
    """
    API que devuelve el HTML del historial de repuestos de balancines con filtros
    """
    # Obtener filtros
    fecha_desde = request.GET.get('fecha_desde')
    fecha_hasta = request.GET.get('fecha_hasta')
    tipo = request.GET.get('tipo')
    busqueda = request.GET.get('busqueda')
    
    # Query base
    historial = HistorialRepuesto.objects.all().select_related('repuesto')
    
    # Aplicar filtros
    if fecha_desde:
        fecha_desde = parse_date(fecha_desde)
        if fecha_desde:
            historial = historial.filter(fecha_movimiento__date__gte=fecha_desde)
    
    if fecha_hasta:
        fecha_hasta = parse_date(fecha_hasta)
        if fecha_hasta:
            historial = historial.filter(fecha_movimiento__date__lte=fecha_hasta)
    
    if tipo:
        historial = historial.filter(tipo_movimiento=tipo)
    
    if busqueda:
        historial = historial.filter(
            Q(repuesto__item__icontains=busqueda) |
            Q(repuesto__descripcion__icontains=busqueda) |
            Q(observaciones__icontains=busqueda)
        )
    
    # Ordenar y limitar
    historial = historial.order_by('-fecha_movimiento')[:100]
    
    # Preparar datos
    actividades = []
    for h in historial:
        actividades.append({
            'tipo': h.tipo_movimiento,
            'repuesto': h.repuesto.item,
            'descripcion': h.repuesto.descripcion,
            'cantidad': h.cantidad,
            'stock_restante': h.stock_restante,
            'observaciones': h.observaciones,
            'fecha': h.fecha_movimiento,
            'origen': 'Balancín'
        })
    
    html = render_to_string('balancines/historial_items.html', {  # ← CORREGIDO
        'actividades': actividades
    })
    return HttpResponse(html)

@login_required
def api_historial_repuestos_adicionales_filtros(request):
    """
    API que devuelve el HTML del historial de repuestos adicionales con filtros
    """
    # Obtener filtros
    fecha_desde = request.GET.get('fecha_desde')
    fecha_hasta = request.GET.get('fecha_hasta')
    tipo = request.GET.get('tipo')
    busqueda = request.GET.get('busqueda')
    
    # Query base
    historial = HistorialAdicional.objects.all().select_related('repuesto', 'usuario')
    
    # Aplicar filtros
    if fecha_desde:
        fecha_desde = parse_date(fecha_desde)
        if fecha_desde:
            historial = historial.filter(fecha_movimiento__date__gte=fecha_desde)
    
    if fecha_hasta:
        fecha_hasta = parse_date(fecha_hasta)
        if fecha_hasta:
            historial = historial.filter(fecha_movimiento__date__lte=fecha_hasta)
    
    if tipo:
        historial = historial.filter(tipo_movimiento=tipo)
    
    if busqueda:
        historial = historial.filter(
            Q(repuesto__item__icontains=busqueda) |
            Q(repuesto__descripcion__icontains=busqueda) |
            Q(observaciones__icontains=busqueda)
        )
    
    # Ordenar y limitar
    historial = historial.order_by('-fecha_movimiento')[:100]
    
    # Preparar datos
    actividades = []
    for h in historial:
        actividades.append({
            'tipo': h.tipo_movimiento,
            'repuesto': h.repuesto.item,
            'descripcion': h.repuesto.descripcion,
            'cantidad': h.cantidad,
            'stock_restante': h.stock_restante,
            'observaciones': h.observaciones,
            'fecha': h.fecha_movimiento,
            'origen': 'Adicional',
            'usuario': h.usuario.nombre if h.usuario else 'Sistema'
        })
    
    html = render_to_string('balancines/historial_items.html', {  # ← CORREGIDO
        'actividades': actividades
    })
    return HttpResponse(html)

@login_required
def api_historial_completo_filtros(request):
    """
    API que devuelve el HTML del historial combinado con filtros
    """
    # Obtener filtros
    fecha_desde = request.GET.get('fecha_desde')
    fecha_hasta = request.GET.get('fecha_hasta')
    tipo = request.GET.get('tipo')
    busqueda = request.GET.get('busqueda')
    
    # Función para aplicar filtros
    def aplicar_filtros(queryset):
        if fecha_desde:
            fd = parse_date(fecha_desde)
            if fd:
                queryset = queryset.filter(fecha_movimiento__date__gte=fd)
        if fecha_hasta:
            fh = parse_date(fecha_hasta)
            if fh:
                queryset = queryset.filter(fecha_movimiento__date__lte=fh)
        if tipo:
            queryset = queryset.filter(tipo_movimiento=tipo)
        return queryset
    
    # Obtener historiales con filtros
    historial_balancin = aplicar_filtros(
        HistorialRepuesto.objects.all().select_related('repuesto')
    )
    
    historial_adicional = aplicar_filtros(
        HistorialAdicional.objects.all().select_related('repuesto', 'usuario')
    )
    
    # Aplicar búsqueda si existe
    if busqueda:
        historial_balancin = historial_balancin.filter(
            Q(repuesto__item__icontains=busqueda) |
            Q(repuesto__descripcion__icontains=busqueda) |
            Q(observaciones__icontains=busqueda)
        )
        historial_adicional = historial_adicional.filter(
            Q(repuesto__item__icontains=busqueda) |
            Q(repuesto__descripcion__icontains=busqueda) |
            Q(observaciones__icontains=busqueda)
        )
    
    # Combinar
    actividades_combinadas = []
    
    for h in historial_balancin[:50]:
        actividades_combinadas.append({
            'tipo': h.tipo_movimiento,
            'repuesto': h.repuesto.item,
            'descripcion': h.repuesto.descripcion,
            'cantidad': h.cantidad,
            'stock_restante': h.stock_restante,
            'observaciones': h.observaciones,
            'fecha': h.fecha_movimiento,
            'origen': 'Balancín'
        })
    
    for h in historial_adicional[:50]:
        actividades_combinadas.append({
            'tipo': h.tipo_movimiento,
            'repuesto': h.repuesto.item,
            'descripcion': h.repuesto.descripcion,
            'cantidad': h.cantidad,
            'stock_restante': h.stock_restante,
            'observaciones': h.observaciones,
            'fecha': h.fecha_movimiento,
            'origen': 'Adicional',
            'usuario': h.usuario.nombre if h.usuario else 'Sistema'
        })
    
    # Ordenar por fecha
    actividades_combinadas.sort(key=lambda x: x['fecha'], reverse=True)
    
    html = render_to_string('balancines/historial_items.html', {  # ← CORREGIDO
        'actividades': actividades_combinadas[:100]
    })
    return HttpResponse(html)
@login_required
def api_dashboard_inventario(request):
    """
    API que devuelve datos JSON para el dashboard de inventario
    """
    periodo = int(request.GET.get('periodo', 30))
    tipo = request.GET.get('tipo', 'todos')
    
    fecha_limite = timezone.now() - timedelta(days=periodo)
    
    # Inicializar datos
    data = {
        'total_entradas': 0,
        'total_salidas': 0,
        'total_movimientos': 0,
        'stock_total': 0,
        'movimientos_dia': {
            'fechas': [],
            'entradas': [],
            'salidas': []
        },
        'distribucion': {
            'entradas': 0,
            'salidas': 0,
            'creaciones': 0,
            'actualizaciones': 0
        },
        'top_repuestos': []
    }
    
    # Calcular stock total
    stock_balancines = RepuestoBalancin.objects.aggregate(total=Sum('cantidad'))['total'] or 0
    stock_adicionales = RepuestoAdicional.objects.aggregate(total=Sum('cantidad'))['total'] or 0
    data['stock_total'] = stock_balancines + stock_adicionales
    
    # Obtener datos según tipo
    if tipo in ['todos', 'balancines']:
        historial_balancin = HistorialRepuesto.objects.filter(
            fecha_movimiento__gte=fecha_limite
        )
        
        data['total_entradas'] += historial_balancin.filter(tipo_movimiento='entrada').count()
        data['total_salidas'] += historial_balancin.filter(tipo_movimiento='salida').count()
        data['total_movimientos'] += historial_balancin.count()
        
        data['distribucion']['entradas'] += historial_balancin.filter(tipo_movimiento='entrada').count()
        data['distribucion']['salidas'] += historial_balancin.filter(tipo_movimiento='salida').count()
        data['distribucion']['creaciones'] += historial_balancin.filter(tipo_movimiento='creacion').count()
        data['distribucion']['actualizaciones'] += historial_balancin.filter(tipo_movimiento='actualizacion').count()
    
    if tipo in ['todos', 'adicionales']:
        historial_adicional = HistorialAdicional.objects.filter(
            fecha_movimiento__gte=fecha_limite
        )
        
        data['total_entradas'] += historial_adicional.filter(tipo_movimiento='entrada').count()
        data['total_salidas'] += historial_adicional.filter(tipo_movimiento='salida').count()
        data['total_movimientos'] += historial_adicional.count()
        
        data['distribucion']['entradas'] += historial_adicional.filter(tipo_movimiento='entrada').count()
        data['distribucion']['salidas'] += historial_adicional.filter(tipo_movimiento='salida').count()
        data['distribucion']['creaciones'] += historial_adicional.filter(tipo_movimiento='creacion').count()
        data['distribucion']['actualizaciones'] += historial_adicional.filter(tipo_movimiento='actualizacion').count()
    
    # Calcular movimientos por día (últimos 7 días)
    for i in range(6, -1, -1):
        dia = timezone.now().date() - timedelta(days=i)
        data['movimientos_dia']['fechas'].append(dia.strftime('%d/%m'))
        
        entradas_dia = 0
        salidas_dia = 0
        
        if tipo in ['todos', 'balancines']:
            entradas_dia += HistorialRepuesto.objects.filter(
                fecha_movimiento__date=dia,
                tipo_movimiento='entrada'
            ).count()
            salidas_dia += HistorialRepuesto.objects.filter(
                fecha_movimiento__date=dia,
                tipo_movimiento='salida'
            ).count()
        
        if tipo in ['todos', 'adicionales']:
            entradas_dia += HistorialAdicional.objects.filter(
                fecha_movimiento__date=dia,
                tipo_movimiento='entrada'
            ).count()
            salidas_dia += HistorialAdicional.objects.filter(
                fecha_movimiento__date=dia,
                tipo_movimiento='salida'
            ).count()
        
        data['movimientos_dia']['entradas'].append(entradas_dia)
        data['movimientos_dia']['salidas'].append(salidas_dia)
    
    # Top 10 repuestos más movidos - CORREGIDO
    from collections import defaultdict
    
    # Inicializar con valores por defecto
    movimientos_repuesto = defaultdict(lambda: {
        'codigo': '', 
        'descripcion': '', 
        'tipo': '', 
        'entradas': 0, 
        'salidas': 0, 
        'total': 0
    })
    
    if tipo in ['todos', 'balancines']:
        for h in HistorialRepuesto.objects.filter(
            fecha_movimiento__gte=fecha_limite
        ).select_related('repuesto')[:100]:
            codigo = h.repuesto.item
            # Inicializar si no existe
            if codigo not in movimientos_repuesto:
                movimientos_repuesto[codigo] = {
                    'codigo': codigo,
                    'descripcion': h.repuesto.descripcion,
                    'tipo': 'balancin',
                    'entradas': 0,
                    'salidas': 0,
                    'total': 0
                }
            
            if h.tipo_movimiento == 'entrada':
                movimientos_repuesto[codigo]['entradas'] += h.cantidad
                movimientos_repuesto[codigo]['total'] += h.cantidad
            elif h.tipo_movimiento == 'salida':
                movimientos_repuesto[codigo]['salidas'] += h.cantidad
                movimientos_repuesto[codigo]['total'] += h.cantidad
    
    if tipo in ['todos', 'adicionales']:
        for h in HistorialAdicional.objects.filter(
            fecha_movimiento__gte=fecha_limite
        ).select_related('repuesto')[:100]:
            codigo = h.repuesto.item
            # Inicializar si no existe
            if codigo not in movimientos_repuesto:
                movimientos_repuesto[codigo] = {
                    'codigo': codigo,
                    'descripcion': h.repuesto.descripcion,
                    'tipo': 'adicional',
                    'entradas': 0,
                    'salidas': 0,
                    'total': 0
                }
            
            if h.tipo_movimiento == 'entrada':
                movimientos_repuesto[codigo]['entradas'] += h.cantidad
                movimientos_repuesto[codigo]['total'] += h.cantidad
            elif h.tipo_movimiento == 'salida':
                movimientos_repuesto[codigo]['salidas'] += h.cantidad
                movimientos_repuesto[codigo]['total'] += h.cantidad
    
    # Ordenar y tomar top 10
    data['top_repuestos'] = sorted(
        [v for v in movimientos_repuesto.values() if v['total'] > 0],
        key=lambda x: x['total'],
        reverse=True
    )[:10]
    
    return JsonResponse(data)