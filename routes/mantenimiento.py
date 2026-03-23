"""
Este archivo contiene las rutas para registrar y consultar actividades de mantenimiento de las máquinas.

Paso a paso:
1. Se importan los módulos necesarios y los modelos de datos.
2. Se define un blueprint para las rutas de mantenimiento.
3. Se maneja la ruta principal para registrar nuevas actividades y mostrar el historial.
4. Se valida que los datos sean correctos antes de guardar.
5. Se actualiza la base de datos y se muestra un mensaje de confirmación.

Este archivo permite llevar un control de las actividades de mantenimiento realizadas.
"""

# Importamos los módulos necesarios y los modelos de datos
from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify
from models import Mantenimiento, Orden, Bloque, Configuracion
from extensions import db
from datetime import datetime, timedelta
import re
import json
import pytz
from flask_babel import _  # Asegúrate de tener flask_babel instalado en requirements.txt

mantenimiento_bp = Blueprint('mantenimiento', __name__, url_prefix='/mantenimiento')
VANCOUVER_TZ = pytz.timezone('America/Vancouver')

# Ruta principal para ver y registrar actividades de mantenimiento
@mantenimiento_bp.route('/', methods=['GET', 'POST'])
def mantenimiento():
    if request.method == 'POST':
        maquina = request.form.get('maquina')
        actividad = request.form.get('actividad')
        descripcion = request.form.get('descripcion', '')
        fecha_str = request.form.get('fecha')
        proxima_fecha_str = request.form.get('proxima_fecha')
        is_done = request.form.get('is_done') == 'on'
        
        base_date = datetime.now(VANCOUVER_TZ)
        if fecha_str:
            try:
                dt = datetime.strptime(fecha_str, '%Y-%m-%d')
                base_date = dt.replace(hour=base_date.hour, minute=base_date.minute, second=base_date.second)
                base_date = VANCOUVER_TZ.localize(base_date)
            except ValueError:
                pass

        if not maquina or not actividad:
            flash(_('Machine and Activity are required.'), 'danger')
        else:
            proxima_fecha = None
            frecuencia_append = ""
            
            if proxima_fecha_str:
                try:
                    proxima_fecha = datetime.strptime(proxima_fecha_str, '%Y-%m-%d')
                    proxima_fecha = VANCOUVER_TZ.localize(proxima_fecha)
                except ValueError:
                    if proxima_fecha_str == '1w':
                        proxima_fecha = base_date + timedelta(weeks=1)
                        frecuencia_append = " (every 1 week)"
                    elif proxima_fecha_str == '1m':
                        proxima_fecha = base_date + timedelta(days=30)
                        frecuencia_append = " (every 1 month)"
                    elif proxima_fecha_str == '2m':
                        proxima_fecha = base_date + timedelta(days=60)
                        frecuencia_append = " (every 2 months)"
                    elif proxima_fecha_str == '6m':
                        proxima_fecha = base_date + timedelta(days=180)
                        frecuencia_append = " (every 6 months)"
                    elif proxima_fecha_str == '1y':
                        proxima_fecha = base_date + timedelta(days=365)
                        frecuencia_append = " (every 1 year)"
            
            if frecuencia_append and not re.search(r'\((cada|every)', actividad, re.IGNORECASE):
                actividad += frecuencia_append
                
            if is_done:
                fecha = base_date
            else:
                fecha = None
                proxima_fecha = base_date

            nuevo = Mantenimiento(
                maquina=maquina,
                actividad=actividad,
                descripcion=descripcion,
                fecha=fecha,
                proxima_fecha=proxima_fecha
            )
            db.session.add(nuevo)
            db.session.commit()
            flash(_('Maintenance logged successfully.'), 'success')
            return redirect(url_for('mantenimiento.mantenimiento'))

    # Build Kanban Board Data
    board_data = [] # List of { 'grupo': 'Fresadoras', 'tipo': 'fresadoras', 'maquinas': [ { 'nombre': 'M1', 'actividades': [...] } ] }
    
    config_maquinas = Configuracion.get_lista('maquinas', default=['A', 'B', 'C', 'D'])
    config_hornos = Configuracion.get_lista('hornos', default=['Horno 1', 'Horno 2', 'Horno 3'])
    config_aspiradoras = Configuracion.get_lista('aspiradoras', default=['Aspiradora 1', 'Aspiradora 2'])
    
    actividades_mant = Configuracion.get_lista('actividades_mantenimiento', default={
        'fresadoras': ['limpieza_general'],
        'hornos': ['calibracion_temperatura'],
        'aspiradoras': ['cambio_filtro']
    })
    if isinstance(actividades_mant, list) and actividades_mant and isinstance(actividades_mant[0], str) and actividades_mant[0].startswith('{'):
        try:
            actividades_mant = json.loads(actividades_mant[0])
        except json.JSONDecodeError:
            actividades_mant = {'fresadoras': [], 'hornos': [], 'aspiradoras': []}
    elif not isinstance(actividades_mant, dict):
        actividades_mant = {'fresadoras': [], 'hornos': [], 'aspiradoras': []}

    # Helper to calculate status
    def get_status(record):
        if not record or not record.proxima_fecha:
            return 'none' # Gray
        
        # Ensure UTC comparison
        now_utc = datetime.now(pytz.utc)
        if record.proxima_fecha.tzinfo is None:
            prox_utc = VANCOUVER_TZ.localize(record.proxima_fecha).astimezone(pytz.utc)
        else:
            prox_utc = record.proxima_fecha.astimezone(pytz.utc)
            
        if prox_utc < now_utc:
            return 'vencido' # Red
        elif prox_utc <= now_utc + timedelta(days=7):
            return 'proximo' # Yellow
        else:
            return 'aldia' # Green
            
    # Helper to calculate days overdue/remaining
    def get_days_diff(record):
        if not record or not record.proxima_fecha:
            return None
            
        now_utc = datetime.now(pytz.utc).date()
        if record.proxima_fecha.tzinfo is None:
            prox_utc = VANCOUVER_TZ.localize(record.proxima_fecha).astimezone(pytz.utc).date()
        else:
            prox_utc = record.proxima_fecha.astimezone(pytz.utc).date()
            
        return (prox_utc - now_utc).days

    # Load all records into memory to avoid N+1 queries
    all_records = Mantenimiento.query.order_by(Mantenimiento.fecha.desc()).all()
    
    # Organize into groups
    groups = [
        {'id': 'fresadoras', 'label': _('Milling Machines'), 'list': config_maquinas},
        {'id': 'hornos', 'label': _('Furnaces'), 'list': config_hornos},
        {'id': 'aspiradoras', 'label': _('Vacuums'), 'list': config_aspiradoras}
    ]
    
    for g in groups:
        grupo_data = {'id': g['id'], 'label': g['label'], 'maquinas': []}
        required_acts = [_(act) for act in actividades_mant.get(g['id'], [])]
        
        for m_name in g['list']:
            maquina_data = {'nombre': m_name, 'actividades': []}
            
            for act_name in required_acts:
                # Find the most recent record for this maquina + act_name
                # Note: Legacy records might have " (cada X semana)" appended, so we check startswith
                recent_record = next((r for r in all_records if r.maquina == m_name and r.actividad.startswith(act_name)), None)
                
                # Only include this activity in the Kanban board if it is actively scheduled (has a proxima_fecha)
                if recent_record and recent_record.proxima_fecha:
                    status = get_status(recent_record)
                    days_diff = get_days_diff(recent_record)
                    
                    maquina_data['actividades'].append({
                        'nombre': act_name,
                        'ultimo_registro': recent_record,
                        'estado': status,
                        'days_diff': days_diff
                    })
                
            # If the machine has scheduled activities, sort them and add the machine to the board
            if maquina_data['actividades']:
                def sort_key(act):
                    order = {'vencido': 0, 'proximo': 1, 'none': 2, 'aldia': 3}
                    return order.get(act['estado'], 4)
                    
                maquina_data['actividades'].sort(key=sort_key)
                
                # Cacular tiempo mas reciente
                recent_time = None
                for act in maquina_data['actividades']:
                    rec = act['ultimo_registro']
                    if rec:
                        t = rec.fecha if rec.fecha else rec.proxima_fecha
                        if t:
                            if t.tzinfo is None:
                                t = pytz.utc.localize(t)
                            if not recent_time or t > recent_time:
                                recent_time = t
                maquina_data['recent_time'] = recent_time
                
                grupo_data['maquinas'].append(maquina_data)
            
        if grupo_data['maquinas']:
            def sort_maq_key(maq):
                t = maq.get('recent_time')
                return t if t else datetime.min.replace(tzinfo=pytz.utc)
            
            grupo_data['maquinas'].sort(key=sort_maq_key, reverse=True)
            board_data.append(grupo_data)

    # API response for home dashboard (next due)
    if request.args.get('api') == '1':
        proximas_validas = [r for r in all_records if r.proxima_fecha]
        def get_utc(dt):
            return VANCOUVER_TZ.localize(dt).astimezone(pytz.utc) if dt.tzinfo is None else dt.astimezone(pytz.utc)
        proximas_validas = [r for r in proximas_validas if get_utc(r.proxima_fecha) >= datetime.now(pytz.utc)]
        # Sort by upcoming date
        proximas_validas.sort(key=lambda r: get_utc(r.proxima_fecha))
        
        # Deduplicate to show only the absolute next for each machine/activity pair
        seen = set()
        unique_proximas = []
        for r in proximas_validas:
            key = (r.maquina, r.actividad)
            if key not in seen:
                seen.add(key)
                unique_proximas.append(r)
                
        return jsonify([
            {
                'id': r.id,
                'maquina': r.maquina,
                'actividad': r.actividad,
                'proxima_fecha': r.proxima_fecha.isoformat()
            }
            for r in unique_proximas
        ])
    # For Schedule New modal (Cascading dropdowns)
    dropdown_data = {}
    for g in groups:
        dropdown_data[g['label']] = {
            'maquinas': g['list'],
            'actividades': [_(act) for act in actividades_mant.get(g['id'], [])]
        }
            
    return render_template(
        'mantenimiento.html',
        board_data=board_data,
        all_records=all_records,
        dropdown_data=json.dumps(dropdown_data)
    )

@mantenimiento_bp.route('/descartar_proxima/<int:mant_id>', methods=['POST'])
def descartar_proxima(mant_id):
    mant = Mantenimiento.query.get_or_404(mant_id)
    # Solo elimina la próxima sugerencia (no el historial)
    db.session.delete(mant)
    db.session.commit()
    flash(_('Upcoming maintenance activity discarded.'), 'success')
    return redirect(url_for('mantenimiento.mantenimiento'))

@mantenimiento_bp.route('/editar/<int:mant_id>', methods=['POST'])
def editar_mantenimiento_kanban(mant_id):
    mant = Mantenimiento.query.get_or_404(mant_id)
    
    maquina = request.form.get('maquina')
    actividad = request.form.get('actividad')
    descripcion = request.form.get('descripcion', '')
    fecha_str = request.form.get('fecha')
    
    if fecha_str:
        try:
            fecha_nueva = datetime.strptime(fecha_str, '%Y-%m-%d')
            now_time = datetime.now(VANCOUVER_TZ)
            fecha_nueva = fecha_nueva.replace(hour=now_time.hour, minute=now_time.minute, second=now_time.second)
            fecha_nueva = VANCOUVER_TZ.localize(fecha_nueva)
            mant.fecha = fecha_nueva
        except ValueError:
            pass
            
    proxima_fecha_str = request.form.get('proxima_fecha')
    if proxima_fecha_str:
        try:
            proxima_fecha = datetime.strptime(proxima_fecha_str, '%Y-%m-%d')
            proxima_fecha = VANCOUVER_TZ.localize(proxima_fecha)
            mant.proxima_fecha = proxima_fecha
        except ValueError:
            if proxima_fecha_str == '1w':
                mant.proxima_fecha = mant.fecha + timedelta(weeks=1)
            elif proxima_fecha_str == '1m':
                mant.proxima_fecha = mant.fecha + timedelta(days=30)
            elif proxima_fecha_str == '2m':
                mant.proxima_fecha = mant.fecha + timedelta(days=60)
            elif proxima_fecha_str == '6m':
                mant.proxima_fecha = mant.fecha + timedelta(days=180)
            elif proxima_fecha_str == '1y':
                mant.proxima_fecha = mant.fecha + timedelta(days=365)
    else:
        mant.proxima_fecha = None
        
    if maquina:
        mant.maquina = maquina
    if actividad:
        mant.actividad = actividad
    if descripcion is not None:
        mant.descripcion = descripcion
        
    db.session.commit()
    flash(_('Maintenance activity updated.'), 'success')
    return redirect(url_for('mantenimiento.mantenimiento'))

@mantenimiento_bp.route('/realizar_proxima/<int:mant_id>', methods=['POST'])
def realizar_proxima(mant_id):
    mant = Mantenimiento.query.get_or_404(mant_id)
    # Extraer intervalo y unidad (Soporte bilingüe)
    match = re.search(r'(?:cada|every) (\d+) (semana|week|mes|month|months|año|year)', mant.actividad, re.IGNORECASE)
    
    fecha = datetime.now(VANCOUVER_TZ)
    proxima_fecha = None
    
    if match:
        intervalo_int = int(match.group(1))
        unidad = match.group(2).lower()
        if unidad in ['semana', 'week']:
            proxima_fecha = fecha + timedelta(weeks=intervalo_int)
        elif unidad in ['mes', 'month', 'months']:
            proxima_fecha = fecha + timedelta(days=30*intervalo_int)
        elif unidad in ['año', 'year']:
            proxima_fecha = fecha + timedelta(days=365*intervalo_int)
        
    nuevo = Mantenimiento(
        maquina=mant.maquina,
        actividad=mant.actividad,
        descripcion=mant.descripcion,
        fecha=fecha,
        proxima_fecha=proxima_fecha
    )
    db.session.add(nuevo)
    db.session.commit()
    flash(_('Maintenance activity logged and next scheduled successfully.'), 'success')
    return redirect(url_for('mantenimiento.mantenimiento'))

@mantenimiento_bp.route('/editar_mantenimiento/<int:mant_id>', methods=['GET', 'POST'])
def editar_mantenimiento(mant_id):
    mant = Mantenimiento.query.get_or_404(mant_id)
    error = None
    # Obtener listas de máquinas y actividades por grupo
    FRESADORAS = Configuracion.get_lista('maquinas', default=['A', 'B', 'C', 'D'])
    hornos = Configuracion.get_lista('hornos', default=['Horno 1', 'Horno 2', 'Horno 3', 'Horno 4'])
    aspiradoras = Configuracion.get_lista('aspiradoras', default=['Aspiradora 1', 'Aspiradora 2', 'Aspiradora 3', 'Aspiradora 4', 'Aspiradora 5'])
    actividades_mant = Configuracion.get_lista('actividades_mantenimiento', default={
        'fresadoras': ['limpieza_general'],
        'hornos': ['calibracion_temperatura'],
        'aspiradoras': ['cambio_filtro']
    })
    if isinstance(actividades_mant, list) and actividades_mant and isinstance(actividades_mant[0], str) and actividades_mant[0].startswith('{'):
        import json
        actividades_mant = json.loads(actividades_mant[0])
    elif not isinstance(actividades_mant, dict):
        actividades_mant = {'fresadoras': [], 'hornos': [], 'aspiradoras': []}
    # Detectar grupo por máquina actual
    grupo = 'fresadoras'
    if mant.maquina in hornos:
        grupo = 'hornos'
    elif mant.maquina in aspiradoras:
        grupo = 'aspiradoras'
    # Pre-fill frequency fields from activity string (Bilingual Support)
    match = re.search(r'(?:cada|every) (\d+) (semana|week|mes|month|año|year)', mant.actividad or '', re.IGNORECASE)
    if match:
        intervalo_edit = int(match.group(1))
        unidad_edit = match.group(2).lower()
    else:
        intervalo_edit = 1
        unidad_edit = 'semana'
    if request.method == 'GET':
        actividad_edit = re.sub(r' \(cada .+\)$', '', mant.actividad or '')
        return render_template(
            'editar_mantenimiento.html',
            mant={
                'id': mant.id,
                'maquina': mant.maquina,
                'actividad_edit': actividad_edit,
                'descripcion': mant.descripcion,
                'fecha': mant.fecha,
                'intervalo_edit': intervalo_edit,
                'unidad_edit': unidad_edit
            },
            grupo=grupo,
            maquinas_dict={'fresadoras': FRESADORAS, 'hornos': hornos, 'aspiradoras': aspiradoras},
            actividades_dict=actividades_mant,
            error=error
        )
    # For POST: update fields and save
    grupo = request.form.get('grupo')
    maquina = request.form.get('maquina')
    actividad = request.form.get('actividad')
    intervalo = request.form.get('intervalo')
    unidad = request.form.get('unidad')
    descripcion = request.form.get('descripcion')
    fecha_str = request.form.get('fecha')
    # Parse date
    try:
        fecha = datetime.strptime(fecha_str, '%Y-%m-%dT%H:%M')
    except Exception:
        fecha = mant.fecha
    mant.maquina = maquina
    
    # Recalculate proxima_fecha
    try:
        if intervalo and unidad:
            intervalo_int = int(intervalo)
            if unidad in ['semana', 'week']:
                proxima_fecha = fecha + timedelta(weeks=intervalo_int)
            elif unidad in ['mes', 'month']:
                proxima_fecha = fecha + timedelta(days=30*intervalo_int)
            elif unidad in ['año', 'year']:
                proxima_fecha = fecha + timedelta(days=365*intervalo_int)
            else:
                proxima_fecha = None
            mant.actividad = f"{actividad} (cada {intervalo} {unidad})"
            mant.proxima_fecha = proxima_fecha
        else:
            mant.actividad = actividad
            mant.proxima_fecha = None
    except Exception:
        pass
        
    mant.descripcion = descripcion
    mant.fecha = fecha
    db.session.commit()
    flash(_('Maintenance activity updated successfully.'))
    return redirect(url_for('mantenimiento.mantenimiento'))

@mantenimiento_bp.route('/eliminar_mantenimiento/<int:mant_id>', methods=['POST'])
def eliminar_mantenimiento(mant_id):
    mant = Mantenimiento.query.get_or_404(mant_id)
    db.session.delete(mant)
    db.session.commit()
    flash(_('Maintenance record deleted successfully.'), 'success')
    return redirect(url_for('mantenimiento.mantenimiento'))

@mantenimiento_bp.route('/documentacion', methods=['GET', 'POST'])
def documentacion():
    # Cargar todas las máquinas de los tres tipos
    fresadoras = Configuracion.get_lista('maquinas', default=['A', 'B', 'C', 'D'])
    hornos = Configuracion.get_lista('hornos', default=['Horno 1', 'Horno 2', 'Horno 3'])
    aspiradoras = Configuracion.get_lista('aspiradoras', default=['Aspiradora 1', 'Aspiradora 2', 'Aspiradora 3'])
    # Guardar/leer datos extendidos en la tabla Configuracion (clave: doc_maquinas)
    doc_data = Configuracion.query.filter_by(clave='doc_maquinas').first()
    if doc_data:
        doc_maquinas = json.loads(doc_data.valor)
    else:
        doc_maquinas = {}
    # Construir lista de máquinas
    maquinas = []
    id_counter = 1
    for tipo, lista in [('Milling Machines', fresadoras), ('Furnaces', hornos), ('Vacuum Cleaners', aspiradoras)]:
        for nombre in lista:
            key = f"{tipo}:{nombre}"
            datos = doc_maquinas.get(key, {'modelo': '', 'serie': '', 'link': '', 'referencia': ''})
            maquinas.append({
                'id': id_counter,
                'tipo': tipo,
                'nombre': nombre,
                'referencia': datos.get('referencia', ''),
                'modelo': datos.get('modelo', ''),
                'serie': datos.get('serie', ''),
                'link': datos.get('link', '')
            })
            id_counter += 1
    if request.method == 'POST':
        # Actualizar datos
        for m in maquinas:
            referencia = request.form.get(f"referencia_{m['id']}", '')
            modelo = request.form.get(f"modelo_{m['id']}", '')
            serie = request.form.get(f"serie_{m['id']}", '')
            link = request.form.get(f"link_{m['id']}", '')
            key = f"{m['tipo']}:{m['nombre']}"
            doc_maquinas[key] = {'referencia': referencia, 'modelo': modelo, 'serie': serie, 'link': link}
        # Guardar en la base de datos
        if not doc_data:
            doc_data = Configuracion(clave='doc_maquinas', valor=json.dumps(doc_maquinas))
            db.session.add(doc_data)
        else:
            doc_data.valor = json.dumps(doc_maquinas)
        db.session.commit()
        return redirect(url_for('mantenimiento.documentacion'))
    return render_template('documentacion.html', maquinas=maquinas)