"""
Script para cargar TODAS las configuraciones de repuestos desde el Excel
Ejecutar: docker exec proyectonuevo-web-1 python manage.py shell < scripts/cargar_todos_tipos_excel.py
"""

import pandas as pd
import os
import re
from apps.balancines.models import TipoBalancin, RepuestoBalancin, ConfiguracionRepuestosPorTipo

# Configuración
EXCEL_PATH = '/app/media/1.0 FORMULARO DE CONTROL DE REACONDICIONAMIETO DE BALANCINES.xls'

# Todas las hojas de tipos de balancines
TIPOS = [
    '4T-501C', '6T-501C', '8T-501C', '10T-501C', '12T-501C',
    '8N/4TR-420C', '10N/4TR-420C', '12N/4TR-420C', '14N/4TR-420C',
    '16N/4TR-420C', '4T/4N-420C'
]

# Mapeo de grupos (por palabras clave en el Excel)
GRUPOS_KEYWORDS = {
    'POLEA': 'POLEAS',
    'POLEAS': 'POLEAS',
    'SEGMENTO 2P': 'SEGMENTOS_2P',
    'SEGMENTO 2N': 'SEGMENTOS_2P',
    'SEGMENTOS 2P': 'SEGMENTOS_2P',
    'SEGMENTO 4P': 'SEGMENTOS_4P',
    'SEGMENTO 4N': 'SEGMENTOS_4P',
    'SEGMENTOS 4P': 'SEGMENTOS_4P',
    'CONJ.': 'CONJUNTOS',
    'CONJUNTO': 'CONJUNTOS',
    'OTRAS PIEZAS': 'OTROS',
}

def detectar_grupo(texto):
    """Detecta el grupo basado en el texto"""
    if pd.isna(texto):
        return 'OTROS'
    
    texto = str(texto).upper()
    for keyword, grupo in GRUPOS_KEYWORDS.items():
        if keyword in texto:
            return grupo
    return 'OTROS'

def limpiar_id(id_str):
    """Limpia un ID de Excel (elimina caracteres no numéricos)"""
    if pd.isna(id_str):
        return None
    id_str = str(id_str).strip()
    # Extraer solo números
    numeros = re.sub(r'[^0-9]', '', id_str)
    if len(numeros) >= 6 and len(numeros) <= 9:
        return numeros
    return None

def crear_o_actualizar_repuesto(id_original, descripcion):
    """Crea o actualiza un repuesto en la tabla RepuestoBalancin"""
    if not id_original:
        return None
    
    repuesto, created = RepuestoBalancin.objects.update_or_create(
        item=id_original,
        defaults={
            'descripcion': descripcion,
            'cantidad': 0,  # Stock inicial 0, se gestionará después
            'ubicacion': 'Por definir',
            'observaciones': f'Cargado desde Excel - {descripcion[:50]}'
        }
    )
    return repuesto

def cargar_todos_tipos():
    print("=" * 60)
    print("🚀 INICIANDO CARGA DE TODOS LOS TIPOS DE BALANCINES")
    print("=" * 60)
    
    # Verificar que el archivo existe
    if not os.path.exists(EXCEL_PATH):
        print(f"❌ ERROR: No se encuentra el archivo {EXCEL_PATH}")
        print("   Copia el Excel a la carpeta media/ del proyecto")
        return
    
    total_conjuntos = 0
    total_componentes = 0
    
    for tipo_nombre in TIPOS:
        print(f"\n📄 PROCESANDO HOJA: {tipo_nombre}")
        print("-" * 40)
        
        try:
            # Leer la hoja del Excel
            df = pd.read_excel(EXCEL_PATH, sheet_name=tipo_nombre, header=None)
            
            # Obtener o crear el tipo de balancín
            tipo, _ = TipoBalancin.objects.get_or_create(
                codigo=tipo_nombre,
                defaults={
                    'tipo': 'soporte',
                    'cantidad_total': 0
                }
            )
            
            # Variables para el procesamiento
            grupo_actual = 'OTROS'
            conjunto_actual = None
            orden_general = 0
            
            # Recorrer el DataFrame buscando IDs
            for idx, row in df.iterrows():
                for col_idx, cell in enumerate(row):
                    if pd.isna(cell):
                        continue
                    
                    cell_str = str(cell).strip()
                    
                    # Detectar títulos de grupos (PR1, PR2, etc. o palabras como POLEAS)
                    if any(keyword in cell_str.upper() for keyword in ['POLEA', 'SEGMENTO', 'CONJ.', 'OTRAS']):
                        nuevo_grupo = detectar_grupo(cell_str)
                        if nuevo_grupo != grupo_actual:
                            grupo_actual = nuevo_grupo
                            print(f"  📌 Grupo detectado: {grupo_actual}")
                            conjunto_actual = None
                            orden_general += 10
                    
                    # Buscar IDs de 8-9 dígitos (posibles IDs de repuestos)
                    id_original = limpiar_id(cell_str)
                    if id_original and len(id_original) >= 7:
                        
                        # Buscar la descripción (está en la misma fila, algunas columnas después)
                        descripcion = ''
                        for offset in range(1, 10):
                            if col_idx + offset < len(row):
                                next_cell = row[col_idx + offset]
                                if pd.notna(next_cell):
                                    next_str = str(next_cell).strip()
                                    # Si no es un número, es la descripción
                                    if not re.match(r'^[0-9]+$', next_str) and len(next_str) > 3:
                                        descripcion = next_str
                                        break
                        
                        # Buscar cantidad
                        cantidad_por_balancin = 1
                        for offset in range(1, 10):
                            if col_idx + offset < len(row):
                                next_cell = row[col_idx + offset]
                                if pd.notna(next_cell):
                                    next_str = str(next_cell).strip()
                                    if re.match(r'^[0-9]+$', next_str):
                                        cantidad_por_balancin = int(float(next_str))
                                        break
                        
                        # Determinar si es un conjunto padre
                        es_conjunto = False
                        if 'POLEA' in descripcion.upper() or 'SEGMENTO' in descripcion.upper() or 'CONJ.' in descripcion.upper():
                            es_conjunto = True
                            print(f"    🟢 Conjunto: {id_original} - {descripcion[:50]}...")
                            total_conjuntos += 1
                        else:
                            print(f"      🔹 Componente: {id_original} - {descripcion[:40]}...")
                            total_componentes += 1
                        
                        # Crear o actualizar el repuesto
                        repuesto = crear_o_actualizar_repuesto(id_original, descripcion)
                        
                        # Crear la configuración
                        config = ConfiguracionRepuestosPorTipo.objects.create(
                            tipo_balancin=tipo,
                            repuesto=repuesto,
                            id_original=id_original,
                            descripcion=descripcion,
                            cantidad_por_balancin=cantidad_por_balancin,
                            cantidad_total=cantidad_por_balancin,  # Se actualizará después
                            es_conjunto=es_conjunto,
                            grupo=grupo_actual,
                            orden=orden_general
                        )
                        
                        # Si es componente de un conjunto, asignar conjunto_padre después
                        orden_general += 1
            
            print(f"  ✅ {tipo_nombre}: {total_conjuntos} conjuntos, {total_componentes} componentes")
            
        except Exception as e:
            print(f"❌ Error en hoja {tipo_nombre}: {e}")
            import traceback
            traceback.print_exc()
    
    print("\n" + "=" * 60)
    print(f"✅✅✅ CARGA COMPLETADA")
    print(f"   Total conjuntos: {total_conjuntos}")
    print(f"   Total componentes: {total_componentes}")
    print("=" * 60)

if __name__ == "__main__":
    cargar_todos_tipos()