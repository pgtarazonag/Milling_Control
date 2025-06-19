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
from flask import Blueprint, render_template, request, redirect, url_for, flash
from models import FresaInventario, FresaInstalada, Configuracion
from extensions import db
from datetime import datetime

# Definimos el blueprint para las rutas de fresas
fresas_bp = Blueprint('fresas', __name__, url_prefix='/fresas')

# Ruta principal para ver, agregar e instalar fresas
@fresas_bp.route('/', methods=['GET', 'POST'])
def fresas():
    error = None
    # Obtener materiales y máquinas desde configuración dinámica
    tipos_material = Configuracion.get_lista('materiales', default=['Zirconia', 'Disilicato', 'PMMA', 'Cera', 'Wax', 'Composite'])
    maquinas = Configuracion.get_lista('maquinas', default=['A', 'B', 'C', 'D'])

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
                fecha_instalacion=datetime.utcnow(),
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
        error=error
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
            fecha_instalacion=datetime.utcnow(),
            modelos_fresados=0
        )
        db.session.add(nueva_instalada)
        db.session.commit()
        flash('Fresa instalada nuevamente.')
    return redirect(url_for('fresas.fresas'))

# Ruta para editar una fresa del inventario
@fresas_bp.route('/editar_inventario/<int:fresa_id>', methods=['POST'])
def editar_inventario(fresa_id):
    fresa = FresaInventario.query.get_or_404(fresa_id)
    fresa.tipo = request.form['tipo']
    fresa.diametro = float(request.form['diametro'])
    fresa.cantidad = int(request.form['cantidad'])
    materiales = request.form.getlist('materiales')
    fresa.materiales = ','.join(materiales)
    db.session.commit()
    flash('Fresa de inventario editada correctamente.')
    return redirect(url_for('fresas.fresas'))

# Ruta para editar una fresa instalada
@fresas_bp.route('/editar_instalada/<int:fresa_id>', methods=['POST'])
def editar_instalada(fresa_id):
    fresa = FresaInstalada.query.get_or_404(fresa_id)
    fresa.tipo = request.form['tipo']
    fresa.diametro = float(request.form['diametro'])
    fresa.maquina = request.form['maquina']
    materiales = request.form.getlist('materiales')
    fresa.materiales = ','.join(materiales)
    db.session.commit()
    flash('Fresa instalada editada correctamente.')
    return redirect(url_for('fresas.fresas'))