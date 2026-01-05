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
    error = None
    grupo = request.args.get('grupo', 'fresadoras')
    FRESADORAS = Configuracion.get_lista('maquinas', default=['A', 'B', 'C', 'D'])
    hornos = Configuracion.get_lista('hornos', default=['Horno 1', 'Horno 2', 'Horno 3', 'Horno 4'])
    aspiradoras = Configuracion.get_lista('aspiradoras', default=['Aspiradora 1', 'Aspiradora 2', 'Aspiradora 3', 'Aspiradora 4', 'Aspiradora 5'])
    if grupo == 'fresadoras':
        maquinas = FRESADORAS
    elif grupo == 'hornos':
        maquinas = hornos
    elif grupo == 'aspiradoras':
        maquinas = aspiradoras
    else:
        maquinas = FRESADORAS
        grupo = 'fresadoras'
    # Actividades personalizadas por grupo
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
    actividades = [ {'nombre': _(act)} for act in actividades_mant.get(grupo, []) ]

    if request.method == 'POST':
        maquina = request.form.get('maquina')
        actividad = request.form.get('actividad')
        intervalo = request.form.get('intervalo')
        unidad = request.form.get('unidad')
        descripcion = request.form.get('descripcion')
        if not maquina or not actividad:
            error = "La máquina y la actividad son obligatorias."
        else:
            fecha = datetime.now(VANCOUVER_TZ)
            try:
                intervalo_int = int(intervalo)
            except (TypeError, ValueError):
                intervalo_int = 1
            if unidad == 'semana':
                proxima_fecha = fecha + timedelta(weeks=intervalo_int)
            elif unidad == 'mes':
                proxima_fecha = fecha + timedelta(days=30*intervalo_int)
            elif unidad == 'año':
                proxima_fecha = fecha + timedelta(days=365*intervalo_int)
            else:
                proxima_fecha = None
            nuevo = Mantenimiento(
                maquina=maquina,
                actividad=f"{actividad} (cada {intervalo} {unidad})" if intervalo and unidad else actividad,
                descripcion=descripcion,
                fecha=fecha,
                proxima_fecha=proxima_fecha
            )
            db.session.add(nuevo)
            db.session.commit()
            flash('Mantenimiento registrado correctamente.')
            return redirect(url_for('mantenimiento.mantenimiento', grupo=grupo))

    registros = Mantenimiento.query.order_by(Mantenimiento.fecha.desc()).all()
    # Calcular próxima fecha para cada registro y extraer intervalo/unidad para edición
    for reg in registros:
        if reg.proxima_fecha:
            continue
            
        # Fallback parsing for legacy records without proxima_fecha
        match = re.search(r'(?:cada|every) (\d+) (semana|week|mes|month|año|year)', reg.actividad, re.IGNORECASE)
        if match:
            intervalo_int = int(match.group(1))
            unidad = match.group(2).lower()
            reg.intervalo_edit = intervalo_int
            reg.unidad_edit = unidad
            # Próxima fecha
            if unidad in ['semana', 'week']:
                reg.proxima_fecha = reg.fecha + timedelta(weeks=intervalo_int)
            elif unidad in ['mes', 'month']:
                reg.proxima_fecha = reg.fecha + timedelta(days=30*intervalo_int)
            elif unidad in ['año', 'year']:
                reg.proxima_fecha = reg.fecha + timedelta(days=365*intervalo_int)
            else:
                reg.proxima_fecha = None
        else:
            reg.intervalo_edit = 1
            reg.unidad_edit = 'semana'
            reg.proxima_fecha = None

    # --- Próximas actividades pendientes ---
    # Para cada máquina y actividad, mostrar la próxima a realizar (la más próxima en el futuro)
    proximas = {}
    for reg in registros:
        if reg.proxima_fecha:
            # Normalizar a UTC si es ingenuo para comparar
            if reg.proxima_fecha.tzinfo is None:
                p_f = VANCOUVER_TZ.localize(reg.proxima_fecha).astimezone(pytz.utc)
            else:
                p_f = reg.proxima_fecha.astimezone(pytz.utc)
                
            if p_f >= datetime.now(pytz.utc):
                key = (reg.maquina, reg.actividad)
                if key not in proximas or reg.proxima_fecha < proximas[key].proxima_fecha:
                    proximas[key] = reg
    proximas_actividades = sorted(proximas.values(), key=lambda r: r.proxima_fecha)

    # Si la petición viene de home, devolver solo la lista (API)
    if request.args.get('api') == '1':
        # Serializar solo los campos necesarios
        return jsonify([
            {
                'id': r.id,
                'maquina': r.maquina,
                'actividad': r.actividad,
                'proxima_fecha': r.proxima_fecha.isoformat() if r.proxima_fecha else None
            }
            for r in proximas_actividades
        ])

    return render_template(
        'mantenimiento.html',
        registros=registros,
        maquinas=maquinas,
        actividades=actividades,
        grupo=grupo,
        error=error,
        proximas_actividades=proximas_actividades
    )

@mantenimiento_bp.route('/descartar_proxima/<int:mant_id>', methods=['POST'])
def descartar_proxima(mant_id):
    mant = Mantenimiento.query.get_or_404(mant_id)
    # Solo elimina la próxima sugerencia (no el historial)
    db.session.delete(mant)
    db.session.commit()
    flash('Próxima actividad descartada.')
    return redirect(url_for('mantenimiento.mantenimiento'))

@mantenimiento_bp.route('/realizar_proxima/<int:mant_id>', methods=['POST'])
def realizar_proxima(mant_id):
    mant = Mantenimiento.query.get_or_404(mant_id)
    # Extraer intervalo y unidad (Soporte bilingüe)
    match = re.search(r'(?:cada|every) (\d+) (semana|week|mes|month|año|year)', mant.actividad, re.IGNORECASE)
    if match:
        intervalo_int = int(match.group(1))
        unidad = match.group(2).lower()
    else:
        intervalo_int = 1
        unidad = 'semana'
    
    fecha = datetime.now(VANCOUVER_TZ)
    if unidad in ['semana', 'week']:
        proxima_fecha = fecha + timedelta(weeks=intervalo_int)
    elif unidad in ['mes', 'month']:
        proxima_fecha = fecha + timedelta(days=30*intervalo_int)
    elif unidad in ['año', 'year']:
        proxima_fecha = fecha + timedelta(days=365*intervalo_int)
    else:
        proxima_fecha = None
        
    nuevo = Mantenimiento(
        maquina=mant.maquina,
        actividad=mant.actividad,
        descripcion=mant.descripcion,
        fecha=fecha,
        proxima_fecha=proxima_fecha
    )
    db.session.add(nuevo)
    db.session.commit()
    flash('Actividad marcada como realizada y próxima programada.')
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
    flash('Registro de mantenimiento eliminado correctamente.')
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