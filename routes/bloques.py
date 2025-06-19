"""
Este archivo contiene las rutas para gestionar los bloques de material.

Paso a paso:
1. Se importan los módulos necesarios y los modelos de datos.
2. Se define un blueprint para las rutas de bloques.
3. Se definen constantes para los tipos de material, grosores y marcas.
4. Se maneja la ruta principal para ver, filtrar y agregar bloques nuevos.
5. Se permite editar y eliminar bloques, guardando historial cuando se elimina un bloque.
6. Se actualiza la base de datos según las acciones del usuario.

Este archivo organiza toda la lógica para el manejo de bloques en el sistema.
"""

# Importamos los módulos necesarios y los modelos de datos
from flask import Blueprint, render_template, request, redirect, url_for
from models import Bloque, BloqueHistorial, Configuracion
from extensions import db
from datetime import datetime

# Definimos el blueprint para las rutas de bloques
bloques_bp = Blueprint('bloques', __name__, url_prefix='/bloques')

# Ruta principal para ver, filtrar y agregar bloques
@bloques_bp.route('/', methods=['GET', 'POST'])
def bloques():
    materiales = Configuracion.get_lista('materiales', default=['Zirconia','Disilicato','PMMA','Cera','Wax','Composite'])
    shades = Configuracion.get_lista('shades', default=['A1','A2','A3','B1','B2','C1','C2'])
    marcas = Configuracion.get_lista('marcas', default=['Vita','Ivoclar','Aidite'])
    grosores = Configuracion.get_lista('grosores', default=['14','16','18','20','22','25'])
    error = None
    # Si se envía el formulario para agregar un bloque nuevo
    if request.method == 'POST':
        material = request.form.get('material', '').strip()
        shade = request.form.get('shade', '').strip()
        grosor_str = request.form.get('grosor', '').strip()
        marca = request.form.get('marca', '').strip() if material == "Zirconia" else None
        cantidad_str = request.form.get('cantidad', '').strip()
        # Validación básica
        if not material or not shade or not grosor_str or not cantidad_str:
            error = 'Todos los campos son obligatorios.'
        else:
            try:
                grosor = int(grosor_str)
                cantidad = int(cantidad_str)
                nuevo = Bloque(
                    material=material,
                    marca=marca,
                    shade=shade,
                    grosor=grosor,
                    cantidad=cantidad,
                    estado='nuevo'
                )
                db.session.add(nuevo)
                db.session.commit()
                return redirect(url_for('bloques.bloques'))
            except ValueError:
                error = 'El grosor y la cantidad deben ser números válidos.'

    # Filtros GET para buscar bloques por material, shade o estado
    material = request.args.get('material')
    shade = request.args.get('shade')
    estado = request.args.get('estado')

    # Consultas para obtener bloques usados y nuevos según los filtros
    query_usados = Bloque.query.filter_by(estado='usado')
    query_nuevos = Bloque.query.filter_by(estado='nuevo')

    if material:
        query_usados = query_usados.filter_by(material=material)
        query_nuevos = query_nuevos.filter_by(material=material)
    if shade:
        query_usados = query_usados.filter_by(shade=shade)
        query_nuevos = query_nuevos.filter_by(shade=shade)

    if estado == 'usado':
        bloques_usados = query_usados.all()
        bloques_nuevos = []
    elif estado == 'nuevo':
        bloques_usados = []
        bloques_nuevos = query_nuevos.all()
    else:
        bloques_usados = query_usados.all()
        bloques_nuevos = query_nuevos.all()

    # Renderizamos la plantilla HTML con los bloques encontrados
    return render_template(
        'bloques.html',
        materiales=materiales,
        shades=shades,
        marcas=marcas,
        grosores=grosores,
        bloques_usados=bloques_usados,
        bloques_nuevos=bloques_nuevos,
        error=error
    )

# Ruta para editar un bloque existente
@bloques_bp.route('/editar/<int:bloque_id>', methods=['GET', 'POST'])
def editar_bloque(bloque_id):
    materiales = Configuracion.get_lista('materiales', default=['Zirconia','Disilicato','PMMA','Cera','Wax','Composite'])
    marcas = Configuracion.get_lista('marcas', default=['Vita','Ivoclar','Aidite'])
    grosores = Configuracion.get_lista('grosores', default=['14','16','18','20','22','25'])
    bloque = Bloque.query.get_or_404(bloque_id)
    if request.method == 'POST':
        # Actualizamos los datos del bloque con los valores del formulario
        bloque.material = request.form['material']
        bloque.shade = request.form['shade']
        bloque.grosor = int(request.form['grosor'])
        bloque.marca = request.form.get('marca') if bloque.material == "Zirconia" else None
        bloque.cantidad = int(request.form['cantidad'])
        bloque.estado = request.form['estado']
        bloque.codigo_barra = request.form.get('codigo_barra') if bloque.estado == 'usado' else None
        bloque.modelos_fresados = int(request.form.get('modelos_fresados', bloque.modelos_fresados or 0))
        # Si editas los códigos de orden fresados, actualízalos aquí
        codigos_orden = request.form.get('codigos_orden_fresados')
        if codigos_orden is not None:
            bloque.codigos_orden_fresados = codigos_orden
        db.session.commit()
        return redirect(url_for('bloques.bloques'))
    return render_template(
        'editar_bloque.html',
        bloque=bloque,
        materiales=materiales,
        marcas=marcas,
        grosores=grosores,
        shades=Configuracion.get_lista('shades', default=['A1','A2','A3','B1','B2','C1','C2'])
    )

# Ruta para eliminar un bloque (lo guarda en el historial antes de eliminar)
@bloques_bp.route('/eliminar/<int:bloque_id>', methods=['POST'])
def eliminar_bloque(bloque_id):
    bloque = Bloque.query.get_or_404(bloque_id)
    # Guardamos el bloque en el historial antes de eliminarlo
    historial = BloqueHistorial(
        bloque_id=bloque.id,
        material=bloque.material,
        marca=bloque.marca,
        shade=bloque.shade,
        grosor=bloque.grosor,
        cantidad=bloque.cantidad,
        codigo_barra=bloque.codigo_barra,
        estado=bloque.estado,
        modelos_fresados=bloque.modelos_fresados,
        codigos_orden_fresados=bloque.codigos_orden_fresados,
        fecha_creacion=bloque.fecha_creacion,
        fecha_eliminacion=datetime.utcnow()
    )
    db.session.add(historial)
    db.session.delete(bloque)
    db.session.commit()
    return redirect(url_for('bloques.bloques'))