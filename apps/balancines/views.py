from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import login, authenticate
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.db.models import Q, Sum, Count, Avg
from django.utils import timezone
from .forms import (
    RegistroForm, BalancinIndividualForm, CambiarEstadoForm, 
    TipoBalancinForm, SeleccionarTorreForm, RegistrarOHForm
)
from .models import (
    TipoBalancin, BalancinIndividual, HistorialBalancin, BalancinOH,
    RepuestoBalancin, RepuestoAdicional, HistorialRepuesto, HistorialAdicional,
    Usuario, Torre, Linea, Seccion, HistorialOH  # ← IMPORTANTE: Agregar HistorialOH
)
from django.http import HttpResponse, JsonResponse
from openpyxl import Workbook
from openpyxl.styles import Font, PatternFill, Alignment
import json
import re


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
        'historial_oh_completo'  # CAMBIADO: antes era 'ordenes_horas'
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
    
    context = {
        'title': f'Balancín {codigo}',
        'balancin': balancin,
        'historial': historial,
        'ordenes_horas': ordenes_horas,
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
            resultados['torres'] = Torre.objects.filter(
                Q(numero_torre__icontains=query) |
                Q(tipo_balancin_ascendente__icontains=query_upper) |
                Q(tipo_balancin_descendente__icontains=query_upper)
            ).select_related('linea', 'seccion')[:20]
            
            # Contar balancines por torre
            for torre in resultados['torres']:
                torre.total_balancines = BalancinIndividual.objects.filter(torre=torre).count()
                torre.ascendentes = BalancinIndividual.objects.filter(torre=torre, sentido='ASCENDENTE').count()
                torre.descendentes = torre.total_balancines - torre.ascendentes
            
            total_resultados += len(resultados['torres'])
        
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
    balancin_filtro = request.GET.get('balancin', '')  # NUEVO: filtro por balancín específico
    
    # ===== PARTE 1: DATOS PARA FILTROS =====
    lineas = Linea.objects.all().order_by('nombre')
    tipos = TipoBalancin.objects.all().order_by('codigo')
    
    # ===== PARTE 2: OBTENER DATOS AGRUPADOS POR BALANCÍN =====
    from django.db import connection
    
    # Construir la consulta base
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
            
            -- Primer OH
            MAX(CASE WHEN numero_oh = 1 THEN TO_CHAR(fecha_oh, 'Mon-YY') END) as oh1_fecha,
            MAX(CASE WHEN numero_oh = 1 THEN anio END) as oh1_anio,
            MAX(CASE WHEN numero_oh = 1 THEN horas_operacion END) as oh1_horas,
            MAX(CASE WHEN numero_oh = 1 THEN backlog END) as oh1_backlog,
            MAX(CASE WHEN numero_oh = 1 THEN dia_semana END) as oh1_dia,
            
            -- Segundo OH
            MAX(CASE WHEN numero_oh = 2 THEN TO_CHAR(fecha_oh, 'Mon-YY') END) as oh2_fecha,
            MAX(CASE WHEN numero_oh = 2 THEN anio END) as oh2_anio,
            MAX(CASE WHEN numero_oh = 2 THEN horas_operacion END) as oh2_horas,
            MAX(CASE WHEN numero_oh = 2 THEN backlog END) as oh2_backlog,
            MAX(CASE WHEN numero_oh = 2 THEN dia_semana END) as oh2_dia,
            
            -- Tercer OH
            MAX(CASE WHEN numero_oh = 3 THEN TO_CHAR(fecha_oh, 'Mon-YY') END) as oh3_fecha,
            MAX(CASE WHEN numero_oh = 3 THEN anio END) as oh3_anio,
            MAX(CASE WHEN numero_oh = 3 THEN horas_operacion END) as oh3_horas,
            MAX(CASE WHEN numero_oh = 3 THEN backlog END) as oh3_backlog,
            MAX(CASE WHEN numero_oh = 3 THEN dia_semana END) as oh3_dia,
            
            -- Cuarto OH
            MAX(CASE WHEN numero_oh = 4 THEN TO_CHAR(fecha_oh, 'Mon-YY') END) as oh4_fecha,
            MAX(CASE WHEN numero_oh = 4 THEN anio END) as oh4_anio,
            MAX(CASE WHEN numero_oh = 4 THEN horas_operacion END) as oh4_horas,
            MAX(CASE WHEN numero_oh = 4 THEN backlog END) as oh4_backlog,
            MAX(CASE WHEN numero_oh = 4 THEN dia_semana END) as oh4_dia,
            
            COUNT(*) as total_ohs,
            balancin_codigo
            
        FROM app_historial_oh
    """
    
    # Agregar filtro por balancín si viene especificado
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
        historial = [dict(zip(columns, row)) for row in cursor.fetchall()]
    
    # ===== APLICAR FILTROS ADICIONALES (en Python) =====
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
        # Determinar estado basado en el último backlog
        if item['total_ohs'] == 0:
            estado = 'sin_oh'
            total_sin_oh += 1
        else:
            # Obtener el último backlog (OH más reciente)
            ultimo_backlog = None
            if item['oh4_backlog'] is not None:
                ultimo_backlog = item['oh4_backlog']
            elif item['oh3_backlog'] is not None:
                ultimo_backlog = item['oh3_backlog']
            elif item['oh2_backlog'] is not None:
                ultimo_backlog = item['oh2_backlog']
            elif item['oh1_backlog'] is not None:
                ultimo_backlog = item['oh1_backlog']
            
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
    
    # ===== APLICAR FILTRO POR ESTADO =====
    if estado_filtro:
        historial = [item for item in historial if item['estado'] == estado_filtro]
    
    # ===== PARTE 4: DATOS PARA GRÁFICO DE BARRAS POR LÍNEA =====
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
    
    # ===== PARTE 5: DATOS PARA GRÁFICO DE BACKLOG POR TORRE =====
    torres_labels = []
    backlog_data = []
    backlog_colors = []
    
    # Limitar a las primeras 20 torres para no saturar el gráfico
    for item in historial[:20]:
        # Crear etiqueta para la torre
        sentido_short = "ASC" if item['sentido'] == 'ASCENDENTE' else "DES"
        etiqueta = f"{item['linea_nombre']} T{item['torre_numero']} {sentido_short}"
        torres_labels.append(etiqueta)
        
        # Obtener el backlog del último OH
        ultimo_backlog = None
        if item['oh4_backlog'] is not None:
            ultimo_backlog = item['oh4_backlog']
        elif item['oh3_backlog'] is not None:
            ultimo_backlog = item['oh3_backlog']
        elif item['oh2_backlog'] is not None:
            ultimo_backlog = item['oh2_backlog']
        elif item['oh1_backlog'] is not None:
            ultimo_backlog = item['oh1_backlog']
        
        if ultimo_backlog is None:
            backlog_data.append(0)
            backlog_colors.append('#6c757d')  # Gris para sin OH
        else:
            backlog_data.append(ultimo_backlog)
            # Color según el valor
            if ultimo_backlog < 0:
                backlog_colors.append('#dc3545')  # Rojo para crítico
            elif ultimo_backlog < 5000:
                backlog_colors.append('#ffc107')  # Amarillo para alerta
            else:
                backlog_colors.append('#28a745')  # Verde para normal
    
    # ===== PARTE 6: TOTALES GENERALES =====
    total_balancines = len(historial)
    total_oh = HistorialOH.objects.count()
    total_oh1 = HistorialOH.objects.filter(numero_oh=1).count()
    total_oh2 = HistorialOH.objects.filter(numero_oh=2).count()
    total_oh3 = HistorialOH.objects.filter(numero_oh=3).count()
    
    balancines_asc = sum(1 for item in historial if item['sentido'] == 'ASCENDENTE')
    balancines_desc = total_balancines - balancines_asc
    
    total_con_oh = total_normal + total_alerta + total_critico
    porcentaje_normal = (total_normal / total_con_oh * 100) if total_con_oh > 0 else 0
    porcentaje_alerta = (total_alerta / total_con_oh * 100) if total_con_oh > 0 else 0
    porcentaje_critico = (total_critico / total_con_oh * 100) if total_con_oh > 0 else 0
    
    # ===== PARTE 7: CONTEXT =====
    context = {
        # Para filtros
        'lineas': lineas,
        'tipos': tipos,
        'linea_filtro': linea_filtro,
        'torre_filtro': torre_filtro,
        'estado_filtro': estado_filtro,
        'balancin_filtro': balancin_filtro,  # NUEVO
        
        # Para la tabla
        'historial': historial,
        
        # Totales generales
        'total_balancines': total_balancines,
        'balancines_asc': balancines_asc,
        'balancines_desc': balancines_desc,
        'total_oh': total_oh,
        'total_oh1': total_oh1,
        'total_oh2': total_oh2,
        'total_oh3': total_oh3,
        
        # Estados
        'total_normal': total_normal,
        'total_alerta': total_alerta,
        'total_critico': total_critico,
        'total_sin_oh': total_sin_oh,
        
        # Porcentajes
        'porcentaje_normal': porcentaje_normal,
        'porcentaje_alerta': porcentaje_alerta,
        'porcentaje_critico': porcentaje_critico,
        
        # Datos para gráfico de barras por línea
        'labels_lineas': json.dumps(labels_lineas),
        'data_normal': json.dumps(data_normal),
        'data_alerta': json.dumps(data_alerta),
        'data_critico': json.dumps(data_critico),
        
        # Datos para gráfico de backlog por torre
        'torres_labels': json.dumps(torres_labels),
        'backlog_data': json.dumps(backlog_data),
        'backlog_colors': json.dumps(backlog_colors),
    }
    
    return render(request, 'balancines/dashboard_oh_nuevo.html', context)

# apps/balancines/views.py - Agrega esta función

from .forms import NuevoOHForm
from .models import HistorialOH, Linea, TipoBalancin
from django.utils import timezone

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
            
            # Verificar que no exista ya ese número de OH
            if HistorialOH.objects.filter(balancin=balancin, numero_oh=numero_oh).exists():
                messages.error(request, f'❌ Ya existe la OH #{numero_oh} para este balancín.')
            else:
                # Obtener datos de la torre y línea
                torre = balancin.torre
                linea_nombre = torre.linea.nombre if torre and torre.linea else 'N/A'
                
                # Determinar tipo de balancín según sentido
                if balancin.sentido == 'ASCENDENTE':
                    tipo = torre.tipo_balancin_ascendente if torre else 'Desconocido'
                else:
                    tipo = torre.tipo_balancin_descendente if torre else 'Desconocido'
                
                # Calcular backlog
                backlog = balancin.rango_horas_cambio_oh - horas_operacion
                
                # Crear el nuevo registro OH
                nuevo_oh = HistorialOH.objects.create(
                    balancin=balancin,
                    linea_nombre=linea_nombre,
                    torre_numero=torre.numero_torre if torre else '0',
                    sentido=balancin.sentido,
                    tipo_balancin=tipo,
                    rango_oh_horas=balancin.rango_horas_cambio_oh,
                    inicio_oc='2014-05-01',  # Valor por defecto
                    horas_promedio_dia=16,    # Valor por defecto
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
        # GET - Mostrar formulario con datos pre-cargados
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

