"""
Este archivo contiene las rutas para consultar el historial de bloques eliminados o modificados.

Paso a paso:
1. Se importa el módulo necesario y el modelo de historial de bloques.
2. Se define un blueprint para las rutas de historial.
3. Se maneja la ruta para mostrar el historial de bloques, ordenado por fecha de eliminación.
4. Se muestra la información en una tabla en la interfaz.

Este archivo permite consultar fácilmente los cambios y eliminaciones de bloques en el sistema.
"""

# Importamos Blueprint para crear un grupo de rutas y render_template para mostrar páginas HTML
from flask import Blueprint, render_template, send_file, request, abort
# Importamos el modelo que representa el historial de bloques en la base de datos
from models import BloqueHistorial, Orden, Bloque, FresaInventario, FresaInstalada, Mantenimiento, OrdenPendiente, Configuracion
from extensions import db
import io
import pandas as pd
from datetime import datetime
import pytz

VANCOUVER_TZ = pytz.timezone('America/Vancouver')

# Creamos un blueprint llamado 'historial' para agrupar las rutas relacionadas con el historial
historial_bp = Blueprint('historial', __name__, url_prefix='/historial')

# Definimos la ruta '/bloques' dentro del blueprint
@historial_bp.route('/bloques')
def historial_bloques():
    # Historial de bloques eliminados/modificados
    bloques_historial = BloqueHistorial.query.order_by(BloqueHistorial.fecha_eliminacion.desc()).all()
    # Bloques usados actuales, ordenados por modelos fresados (mayor a menor)
    bloques_usados_ordenados = Bloque.query.filter_by(estado='usado').order_by(Bloque.modelos_fresados.desc()).all()
    
    # Get materials for filter
    materiales = Configuracion.get_lista('materiales', default=['Zirconia','Disilicato','PMMA','Cera','Wax','Composite'])
    shades = Configuracion.get_lista('shades', default=['A1','A2','A3','B1','B2','C1','C2'])
    marcas = Configuracion.get_lista('marcas', default=['Vita','Ivoclar','Aidite'])
    grosores = Configuracion.get_lista('grosores', default=['14','16','18','20','22','25'])
    
    return render_template('historial_bloques.html', 
                           bloques_historial=bloques_historial, 
                           bloques_usados_ordenados=bloques_usados_ordenados,
                           materiales=materiales,
                           shades=shades,
                           marcas=marcas,
                           grosores=grosores)

@historial_bp.route('/eliminar/<int:historial_id>', methods=['POST'])
def eliminar_historial_permanente(historial_id):
    from flask import flash, redirect, url_for
    registro = BloqueHistorial.query.get_or_404(historial_id)
    db.session.delete(registro)
    db.session.commit()
    flash('Registro de historial eliminado permanentemente.', 'success')
    return redirect(url_for('historial.historial_bloques'))

@historial_bp.route('/editar/<int:historial_id>', methods=['POST'])
def editar_historial(historial_id):
    from flask import flash, redirect, url_for
    registro = BloqueHistorial.query.get_or_404(historial_id)
    
    registro.material = request.form.get('material')
    registro.marca = request.form.get('marca')
    registro.shade = request.form.get('shade')
    registro.grosor = request.form.get('grosor')
    registro.codigo_barra = request.form.get('codigo_barra')
    # Optional: modelo, etc.
    
    db.session.commit()
    flash('Registro de historial actualizado.', 'success')
    return redirect(url_for('historial.historial_bloques'))

@historial_bp.route('/restaurar/<int:historial_id>', methods=['POST'])
def restaurar_bloque(historial_id):
    from flask import flash, redirect, url_for
    registro = BloqueHistorial.query.get_or_404(historial_id)
    
    # Create new Block from History
    nuevo_bloque = Bloque(
        material=registro.material,
        marca=registro.marca,
        shade=registro.shade,
        grosor=registro.grosor,
        cantidad=registro.cantidad if registro.cantidad is not None else 1,
        codigo_barra=registro.codigo_barra,
        codigo_referencia=registro.codigo_referencia,
        estado='usado', # Restore as 'Used' per request
        modelos_fresados=registro.modelos_fresados,
        codigos_orden_fresados=registro.codigos_orden_fresados,
        fecha_creacion=registro.fecha_creacion if registro.fecha_creacion else datetime.utcnow()
    )
    
    db.session.add(nuevo_bloque)
    db.session.delete(registro)
    db.session.commit()
    
    flash('Bloque restaurado exitosamente a la lista de usados.', 'success')
    return redirect(url_for('historial.historial_bloques'))

@historial_bp.route('/descargar', methods=['GET'])
def descargar_historial():
    tablas = {
        'bloques_historial': BloqueHistorial,
        'ordenes': Orden,
        'bloques': Bloque,
        'fresa_inventario': FresaInventario,
        'fresa_instalada': FresaInstalada,
        'mantenimiento': Mantenimiento,
        'orden_pendiente': OrdenPendiente
    }
    seleccionadas = request.args.getlist('tablas')
    descargar_bd = request.args.get('descargar_bd') == '1'
    if descargar_bd or not seleccionadas:
        seleccionadas = list(tablas.keys())
    # Crear Excel en memoria
    output = io.BytesIO()
    try:
        with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
            for nombre, modelo in tablas.items():
                if nombre not in seleccionadas:
                    continue
                try:
                    # Traer filas vía ORM y serializar a dicts
                    rows = modelo.query.all()
                    data = []
                    cols = [c.name for c in modelo.__table__.columns]
                    for obj in rows:
                        item = {}
                        for col in cols:
                            val = getattr(obj, col, None)
                            if isinstance(val, datetime):
                                try:
                                    val = val.isoformat()
                                except Exception:
                                    pass
                            item[col] = val
                        data.append(item)
                    df = pd.DataFrame(data, columns=cols)
                    
                    # Translation Mapping
                    column_map = {
                        'id': 'ID',
                        'bloque_id': 'Block ID',
                        'codigos_caso': 'Case Codes',
                        'material': 'Material',
                        'marca': 'Brand',
                        'shade': 'Shade',
                        'codigo_barra': 'Barcode',
                        'maquina': 'Machine',
                        'cantidad_modelos': 'Model Count',
                        'fecha_creacion': 'Creation Date',
                        'grosor': 'Thickness',
                        'cantidad': 'Quantity',
                        'estado': 'Status',
                        'codigo_referencia': 'Reference Code',
                        'modelos_fresados': 'Milled Models',
                        'codigos_orden_fresados': 'Milled Order Codes',
                        'fecha_eliminacion': 'Deletion Date',
                        'tipo': 'Type',
                        'diametro': 'Diameter',
                        'materiales': 'Materials',
                        'fecha_instalacion': 'Installation Date',
                        'fecha_reemplazo': 'Replacement Date',
                        'posicion': 'Position',
                        'vida_util_estimada': 'Est. Lifespan',
                        'uso_acumulado': 'Accumulated Usage',
                        'descripcion': 'Description',
                        'usuario': 'User',
                        'fecha': 'Date',
                        'orden_id': 'Order ID'
                    }
                    df.rename(columns=column_map, inplace=True)
                    
                    # Apply reference code prefix if configured
                    ref_code_prefix = Configuracion.get_valor('ref_code_prefix', default='')
                    if ref_code_prefix and 'Reference Code' in df.columns:
                        df['Reference Code'] = df['Reference Code'].apply(
                            lambda x: f"{ref_code_prefix}{x}" if x and str(x).strip() and str(x) != 'None' else x
                        )
                except Exception:
                    cols = [c.name for c in modelo.__table__.columns]
                    df = pd.DataFrame(columns=cols)
                # Translate sheet names to English
                sheet_name_map = {
                    'bloques_historial': 'Block History',
                    'ordenes': 'Orders',
                    'bloques': 'Blocks',
                    'fresa_inventario': 'Mill Inventory',
                    'fresa_instalada': 'Installed Mills',
                    'mantenimiento': 'Maintenance',
                    'orden_pendiente': 'Pending Orders'
                }
                sheet_name = sheet_name_map.get(nombre, nombre)[:31]  # Max 31 chars for Excel
                df.to_excel(writer, sheet_name=sheet_name, index=False)
                # Ajustes de ancho
                try:
                    worksheet = writer.sheets[sheet_name]
                    for idx, col in enumerate(df.columns):
                        max_len = 10
                        if not df.empty:
                            max_len = max(max_len, int(df[col].astype(str).str.len().max()))
                        width = min(max_len + 2, 60)
                        worksheet.set_column(idx, idx, width)
                except Exception:
                    pass
        output.seek(0)
    except Exception as e:
        # Si no está el engine xlsxwriter instalado, devolver error claro
        abort(500, description=f"Error generando Excel: {e}")
    return send_file(
        output,
        as_attachment=True,
        download_name=f"milling_history_{datetime.now(VANCOUVER_TZ).strftime('%Y%m%d_%H%M')}.xlsx",
        mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
    )

@historial_bp.route('/reporte_semanal', methods=['GET'])
def reporte_semanal():
    # Semanas seleccionadas (formato YYYY-Www)
    start_week_str = request.args.get('start_week')
    end_week_str = request.args.get('end_week')
    
    # Material filter
    selected_materials = request.args.getlist('materiales')
    if not selected_materials:
        # If none selected, assume all (or handle empty) - user said default all.
        # But if the UI sends nothing, it usually means nothing selected.
        # If it's a GET link, maybe we default to all.
        pass # We will handle "if not selected_materials" as "no filter" (All) or specific logic.

    # If simple 'semana' is passed (backward capability) or just one provided
    if not start_week_str and request.args.get('semana'):
        start_week_str = request.args.get('semana')
    if not end_week_str:
        end_week_str = start_week_str

    if not start_week_str:
        # Default to current week
        now = datetime.now(VANCOUVER_TZ)
        year, week, _ = now.isocalendar()
        start_week_str = f"{year}-W{week:02d}"
        end_week_str = start_week_str

    try:
        # 1. Calculate Date Range
        # Parse Start Week (Monday)
        s_year, s_week = map(int, start_week_str.split('-W'))
        start_date_naive = datetime.fromisocalendar(s_year, s_week, 1) # Monday
        start_date = VANCOUVER_TZ.localize(datetime.combine(start_date_naive, datetime.min.time()))

        # Parse End Week (Sunday)
        e_year, e_week = map(int, end_week_str.split('-W'))
        end_date_naive = datetime.fromisocalendar(e_year, e_week, 7) # Sunday
        end_date = VANCOUVER_TZ.localize(datetime.combine(end_date_naive, datetime.max.time()))
        
    except ValueError:
         abort(400, description="Invalid Week Format")
    
    # 2. Snapshot de Inventario Actual (Bloques Nuevos)
    # Agrupado por Material, Shade, Marca, Grosor, RefCode
    inv_query_base = Bloque.query.filter_by(estado='nuevo')
    if selected_materials:
        inv_query_base = inv_query_base.filter(Bloque.material.in_(selected_materials))
        
    inv_query = inv_query_base.all()
    inventory_map = {} # Key: (Material, Shade, Marca, Grosor, RefCode), Value: count
    for b in inv_query:
        key = (b.material, b.shade, b.marca or '', b.grosor or '', b.codigo_referencia or '')
        inventory_map[key] = inventory_map.get(key, 0) + (b.cantidad or 0)

    # 3. Fetch Weekly Usage (Active + Hist)
    active_used_query = Bloque.query.filter(
        Bloque.estado == 'usado',
        Bloque.fecha_creacion >= start_date,
        Bloque.fecha_creacion <= end_date
    )
    if selected_materials:
        active_used_query = active_used_query.filter(Bloque.material.in_(selected_materials))
    active_used = active_used_query.all()

    hist_used_query = BloqueHistorial.query.filter(
        BloqueHistorial.estado == 'usado',
        BloqueHistorial.fecha_creacion >= start_date,
        BloqueHistorial.fecha_creacion <= end_date
    )
    if selected_materials:
        hist_used_query = hist_used_query.filter(BloqueHistorial.material.in_(selected_materials))
    hist_used = hist_used_query.all()

    # Data Structure for Usage: 
    # Key: (Material, Shade, Marca, Grosor, RefCode)
    # Value: { "YYYY-Www": Count, ... }
    usage_map = {} 

    all_blocks = active_used + hist_used
    
    # Helper to get week string
    def get_week_str(dt_obj):
        # Ensure dt_obj is timezone aware or handle consistently
        if dt_obj.tzinfo is None:
             dt_obj = pytz.utc.localize(dt_obj)
        dt_vancouver = dt_obj.astimezone(VANCOUVER_TZ)
        y, w, _ = dt_vancouver.isocalendar()
        return f"{y}-W{w:02d}"

    weeks_in_range = set()
    
    # Process Standard 'Used' blocks (Zirconia, etc)
    for b in all_blocks:
        key = (b.material, b.shade, b.marca or '', b.grosor or '', b.codigo_referencia or '')
        w_str = get_week_str(b.fecha_creacion)
        weeks_in_range.add(w_str)
        
        if key not in usage_map:
            usage_map[key] = {}
        
        usage_map[key][w_str] = usage_map[key].get(w_str, 0) + 1

    # Process Titanium direct deductions from Audit Log
    titanium_logs_query = LogInventario.query.filter(
        LogInventario.accion == 'CONSUMO_TITANIO',
        LogInventario.fecha >= start_date,
        LogInventario.fecha <= end_date
    )
    titanium_logs = titanium_logs_query.all()
    
    import json
    import re
    
    for log in titanium_logs:
        mat, shade, brand, grosor, ref_code = None, None, None, None, None
        qty = 0
        if log.detalles:
            try:
                data = json.loads(log.detalles)
                mat = data.get('material')
                shade = data.get('shade')
                brand = data.get('marca')
                grosor = data.get('grosor')
                ref_code = data.get('codigo_referencia')
                qty = data.get('qty', 1)
            except Exception:
                pass
                
        if not mat: # Fallback for legacy logs before JSON detailing
            match = re.search(r'(?i)consumed\s+(\d+)\s+units', log.descripcion)
            if match:
                qty = int(match.group(1))
            else:
                qty = 1
                
            b = Bloque.query.get(log.bloque_id)
            if not b:
                b = BloqueHistorial.query.filter_by(id=log.bloque_id).first()
            if b:
                mat = b.material
                shade = b.shade
                brand = b.marca
                grosor = b.grosor
                ref_code = b.codigo_referencia
        
        if not mat:
            mat = 'Titanio'
            brand = 'Unknown'
            shade = 'Unknown'
            grosor = ''
            ref_code = 'Unknown'
            
        if selected_materials and mat not in selected_materials:
            continue
            
        key = (mat, shade, brand or '', grosor or '', ref_code or '')
        w_str = get_week_str(log.fecha)
        weeks_in_range.add(w_str)
        
        if key not in usage_map:
            usage_map[key] = {}
            
        usage_map[key][w_str] = usage_map[key].get(w_str, 0) + qty

    # 4. Combine Data
    all_keys = set(inventory_map.keys()) | set(usage_map.keys())
    
    # Sort weeks columns
    sorted_weeks = sorted(list(weeks_in_range))
    # If range was requested but no data found, generate weeks manually? 
    # For now, let's stick to weeks with data + the requested range boundaries if we want to be strict, 
    # but pandas pivot is easier if we just list what we have.
    # To be safe, let's at least ensure start and end week columns exist if user asked for them?
    # User asked for "each week will be a different column".
    
    data = []
    for key in all_keys:
        mat, shade, brand, grosor, ref_code = key # Unpack 5 items
        
        row = {
            'Material': mat,
            'Shade': shade,
            'Brand': brand,
            'Thickness': grosor,
            'Ref Code': ref_code,
            'Current Inventory': inventory_map.get(key, 0)
        }
        
        # Add usage per week
        item_usage = usage_map.get(key, {})
        for w in sorted_weeks:
            row[f"Usage {w}"] = item_usage.get(w, 0)
            
        data.append(row)
    
    # 5. Generate Excel
    if not data:
        # Empty case
        df = pd.DataFrame(columns=['Material', 'Shade', 'Brand', 'Thickness', 'Ref Code', 'Current Inventory'])
    else:
        df = pd.DataFrame(data)
        # Sort
        # First columns fixed
        cols = ['Material', 'Brand', 'Thickness', 'Shade', 'Ref Code', 'Current Inventory']
        # Add week columns dynamically
        week_cols = [f"Usage {w}" for w in sorted_weeks]
        
        # Reorder df columns
        final_cols = cols + week_cols
        # Ensure all cols exist (some rows might miss keys if created by dict)
        df = df.reindex(columns=final_cols, fill_value=0)
        
        df = df.sort_values(by=['Material', 'Brand', 'Thickness', 'Shade'])
        
        # Apply reference code prefix if configured
        ref_code_prefix = Configuracion.get_valor('ref_code_prefix', default='')
        if ref_code_prefix and 'Ref Code' in df.columns:
            df['Ref Code'] = df['Ref Code'].apply(
                lambda x: f"{ref_code_prefix}{x}" if x and str(x).strip() and str(x) != 'None' else x
            )
    
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
        df.to_excel(writer, sheet_name='Weekly Report', index=False)
        
        workbook = writer.book
        worksheet = writer.sheets['Weekly Report']
        
        # Formats
        header_fmt = workbook.add_format({'bold': True, 'bg_color': '#D3D3D3', 'border': 1})
        num_fmt = workbook.add_format({'num_format': '#,##0'})
        
        # Headers
        for col_num, value in enumerate(df.columns.values):
            worksheet.write(0, col_num, value, header_fmt)
            worksheet.set_column(col_num, col_num, 15)

    output.seek(0)
    filename = f"Usage_Report_{start_week_str}_to_{end_week_str}.xlsx"
    return send_file(
        output,
        as_attachment=True,
        download_name=filename,
        mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
    )