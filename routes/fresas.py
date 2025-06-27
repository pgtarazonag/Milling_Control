"""
Este archivo contiene las rutas para gestionar las fresas (herramientas de corte).

Paso a paso:
1. Se importan los módulos necesarios y los modelos de datos.
2. Se define un blueprint para las rutas de fresas.
3. Se permite agregar fresas al inventario y registrar su instalación en máquinas.
4. Se pueden editar y eliminar fresas tanto del inventario como de las instaladas.
5. Se actualiza la base de datos según las acciones del usuario.

Este archivo organiza toda la lógica para el manejo de fresas en el sistema.
"""

# Importamos los módulos necesarios y los modelos de datos
from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify
from models import FresaInventario, FresaInstalada, Configuracion
from extensions import db
from datetime import datetime
import pytz
import json
VANCOUVER_TZ = pytz.timezone('America/Vancouver')

# Definimos el blueprint para las rutas de fresas
fresas_bp = Blueprint('fresas', __name__, url_prefix='/fresas')

# Ruta principal para ver, agregar e instalar fresas
@fresas_bp.route('/', methods=['GET', 'POST'])
def fresas():
    error = None
    # Obtener materiales y máquinas desde configuración dinámica
    tipos_material = Configuracion.get_lista('materiales', default=['Zirconia', 'Disilicato', 'PMMA', 'Cera', 'Wax', 'Composite'])
    maquinas = Configuracion.get_lista('maquinas', default=['A', 'B', 'C', 'D'])

    tipos_fresa = []
    try:
        fresas_maquinas = Configuracion.get_lista('fresas_maquinas')
        if isinstance(fresas_maquinas, dict):
            tipos_fresa = list(fresas_maquinas.keys())
        elif fresas_maquinas and isinstance(fresas_maquinas, list) and isinstance(fresas_maquinas[0], str) and fresas_maquinas[0].startswith('{'):
            tipos_fresa = list(json.loads(fresas_maquinas[0]).keys())
    except Exception:
        pass
    # fallback: si no hay tipos_fresa definidos, usar los del inventario
    if not tipos_fresa:
        tipos_fresa = sorted(list(set(f.tipo for f in FresaInventario.query.all())))

    # Si se envía el formulario para agregar una fresa al inventario
    if request.method == 'POST' and 'agregar_inventario' in request.form:
        tipo = request.form['tipo']
        cantidad = int(request.form['cantidad'])
        materiales = request.form.getlist('materiales')
        materiales_str = ','.join(materiales)
        # Buscamos si ya existe una fresa igual en el inventario
        existente = FresaInventario.query.filter_by(tipo=tipo, materiales=materiales_str).first()
        if existente:
            existente.cantidad += cantidad
        else:
            nueva = FresaInventario(tipo=tipo, cantidad=cantidad, materiales=materiales_str)
            db.session.add(nueva)
        db.session.commit()
        return redirect(url_for('fresas.fresas'))

    # Si se envía el formulario para instalar una fresa desde el inventario
    if request.method == 'POST' and 'instalar_fresa' in request.form:
        tipo = request.form['tipo_diametro_instalar']
        maquina = request.form['maquina_instalar']
        inventario = FresaInventario.query.filter_by(tipo=tipo).filter(FresaInventario.cantidad > 0).first()
        if inventario and inventario.cantidad > 0:
            inventario.cantidad -= 1
            nueva_instalada = FresaInstalada(
                tipo=tipo,
                maquina=maquina,
                materiales=inventario.materiales,
                fecha_instalacion=datetime.now(VANCOUVER_TZ),
                modelos_fresados=0
            )
            db.session.add(nueva_instalada)
            db.session.commit()
        else:
            error = "No hay suficiente inventario para instalar esa fresa."
        return redirect(url_for('fresas.fresas'))

    fresas_inventario = FresaInventario.query.order_by(FresaInventario.tipo).all()
    fresas_instaladas = FresaInstalada.query.order_by(FresaInstalada.fecha_instalacion.desc()).all()

    return render_template(
        'fresas.html',
        fresas_inventario=fresas_inventario,
        fresas_instaladas=fresas_instaladas,
        maquinas=maquinas,
        tipos_material=tipos_material,
        error=error,
        fresas_maquinas=fresas_maquinas,
        tipos_fresa=tipos_fresa
    )

# Ruta para eliminar una fresa instalada
@fresas_bp.route('/eliminar_instalada/<int:fresa_id>', methods=['POST'])
def eliminar_instalada(fresa_id):
    fresa = FresaInstalada.query.get_or_404(fresa_id)
    tipo = fresa.tipo
    diametro = fresa.diametro
    materiales = fresa.materiales
    db.session.delete(fresa)
    db.session.commit()

    # Si el usuario quiere reinstalar una igual, lo hacemos aquí
    inventario = FresaInventario.query.filter_by(tipo=tipo, diametro=diametro, materiales=materiales).filter(FresaInventario.cantidad > 0).first()
    if inventario and request.form.get('reinstalar') == 'si':
        inventario.cantidad -= 1
        nueva_instalada = FresaInstalada(
            tipo=tipo,
            diametro=diametro,
            maquina=fresa.maquina,
            materiales=materiales,
            fecha_instalacion=datetime.now(VANCOUVER_TZ),
            modelos_fresados=0
        )
        db.session.add(nueva_instalada)
        db.session.commit()
        flash('Fresa instalada nuevamente.')
    return redirect(url_for('fresas.fresas'))

# Ruta para editar una fresa del inventario
@fresas_bp.route('/editar_inventario/<int:fresa_id>', methods=['GET', 'POST'])
def editar_inventario(fresa_id):
    fresa = FresaInventario.query.get_or_404(fresa_id)
    if request.method == 'POST':
        fresa.tipo = request.form['tipo']
        fresa.diametro = float(request.form['diametro']) if request.form.get('diametro') else None
        fresa.cantidad = int(request.form['cantidad'])
        materiales = request.form.get('materiales', '')
        fresa.materiales = materiales
        db.session.commit()
        flash('Fresa de inventario editada correctamente.')
        return redirect(url_for('fresas.fresas'))
    tipos_fresa = []
    try:
        fresas_maquinas = Configuracion.get_lista('fresas_maquinas')
        if isinstance(fresas_maquinas, dict):
            tipos_fresa = list(fresas_maquinas.keys())
        elif fresas_maquinas and isinstance(fresas_maquinas, list) and isinstance(fresas_maquinas[0], str) and fresas_maquinas[0].startswith('{'):
            tipos_fresa = list(json.loads(fresas_maquinas[0]).keys())
    except Exception:
        pass
    # fallback: si no hay tipos_fresa definidos, usar los del inventario
    if not tipos_fresa:
        tipos_fresa = sorted(list(set(f.tipo for f in FresaInventario.query.all())))
    return render_template('editar_fresa.html', fresa=fresa, tipos_fresa=tipos_fresa)

# Ruta para editar una fresa instalada
@fresas_bp.route('/editar_instalada/<int:fresa_id>', methods=['GET', 'POST'])
def editar_instalada(fresa_id):
    fresa = FresaInstalada.query.get_or_404(fresa_id)
    if request.method == 'POST':
        fresa.tipo = request.form['tipo']
        fresa.maquina = request.form['maquina']
        materiales = request.form.get('materiales', '')
        fresa.materiales = materiales
        fresa.modelos_fresados = int(request.form.get('modelos_fresados', 0))
        db.session.commit()
        flash('Fresa instalada editada correctamente.')
        return redirect(url_for('fresas.fresas'))
    # Obtener tipos de fresa y máquinas definidos en configuración
    tipos_fresa = []
    try:
        fresas_maquinas = Configuracion.get_lista('fresas_maquinas')
        if isinstance(fresas_maquinas, dict):
            tipos_fresa = list(fresas_maquinas.keys())
        elif fresas_maquinas and isinstance(fresas_maquinas, list) and isinstance(fresas_maquinas[0], str) and fresas_maquinas[0].startswith('{'):
            tipos_fresa = list(json.loads(fresas_maquinas[0]).keys())
    except Exception:
        pass
    if not tipos_fresa:
        tipos_fresa = sorted(list(set(f.tipo for f in FresaInventario.query.all())))
    maquinas = Configuracion.get_lista('maquinas', default=['A', 'B', 'C', 'D'])
    return render_template('editar_fresa_instalada.html', fresa=fresa, tipos_fresa=tipos_fresa, maquinas=maquinas)

# Ruta API para obtener fresas nuevas (cantidad > 0)
@fresas_bp.route('/api/fresas-nuevas')
def api_fresas_nuevas():
    orden = request.args.get('orden', 'tipo')
    query = FresaInventario.query.filter(FresaInventario.cantidad > 0)
    if orden == 'tipo':
        query = query.order_by(FresaInventario.tipo)
    elif orden == 'cantidad_desc':
        query = query.order_by(FresaInventario.cantidad.desc())
    elif orden == 'cantidad_asc':
        query = query.order_by(FresaInventario.cantidad)
    fresas = query.all()
    data = []
    for f in fresas:
        data.append({
            'tipo': f.tipo,
            'diametro': f.diametro,
            'materiales': f.materiales,
            'cantidad': f.cantidad,
            'fecha': f.fecha_registro.astimezone(VANCOUVER_TZ).strftime('%Y-%m-%d %H:%M') if f.fecha_registro else ''
        })
    return jsonify(data)

@fresas_bp.route('/modificar_cantidad/<int:fresa_id>/<accion>', methods=['POST'])
def modificar_cantidad(fresa_id, accion):
    fresa = FresaInventario.query.get_or_404(fresa_id)
    if accion == 'incrementar':
        fresa.cantidad += 1
        db.session.commit()
        flash('Cantidad incrementada.', 'success')
    elif accion == 'decrementar':
        if fresa.cantidad > 0:
            fresa.cantidad -= 1
            db.session.commit()
            flash('Cantidad decrementada.', 'success')
        else:
            flash('No se puede decrementar más.', 'warning')
    else:
        flash('Acción no válida.', 'danger')
    return redirect(url_for('fresas.fresas'))

# Ruta para eliminar una fresa del inventario
@fresas_bp.route('/eliminar_inventario/<int:fresa_id>', methods=['POST'])
def eliminar_inventario(fresa_id):
    fresa = FresaInventario.query.get_or_404(fresa_id)
    db.session.delete(fresa)
    db.session.commit()
    flash('Fresa eliminada del inventario correctamente.', 'success')
    return redirect(url_for('fresas.fresas'))