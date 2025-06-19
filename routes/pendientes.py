"""
Este archivo contiene las rutas para gestionar los casos pendientes de fresado.
Permite agregar códigos escaneados (cada vez que el escáner envía un ENTER) y mostrar la lista de casos pendientes.
El usuario puede seleccionar uno o varios códigos de la lista para crear una orden grupal, donde todos compartirán los mismos datos (shade, material, bloque, etc.).
"""
from flask import Blueprint, render_template, request, redirect, url_for, flash
from models import OrdenPendiente
from extensions import db
from datetime import datetime

# Creamos un blueprint para las rutas de casos pendientes
detener_bp = Blueprint('pendientes', __name__, url_prefix='/pendientes')

# Ruta para mostrar y agregar códigos escaneados
@detener_bp.route('/', methods=['GET', 'POST'])
def pendientes():
    if request.method == 'POST':
        # Obtenemos el código escaneado del formulario
        codigo_orden = request.form.get('codigo_orden', '').strip()
        # Si el campo no está vacío y no existe ya en la lista, lo agregamos
        if codigo_orden and not OrdenPendiente.query.filter_by(codigo_orden=codigo_orden).first():
            nuevo = OrdenPendiente(codigo_orden=codigo_orden)
            db.session.add(nuevo)
            db.session.commit()
            flash('Código agregado a la lista de pendientes.')
        return redirect(url_for('pendientes.pendientes'))

    # Obtenemos todos los códigos pendientes
    pendientes = OrdenPendiente.query.order_by(OrdenPendiente.fecha_escaneo.asc()).all()
    # Renderizamos la plantilla con la lista de pendientes
    return render_template('pendientes.html', pendientes=pendientes)

@detener_bp.route('/eliminar_pendiente/<int:pendiente_id>', methods=['POST'])
def eliminar_pendiente(pendiente_id):
    pendiente = OrdenPendiente.query.get_or_404(pendiente_id)
    db.session.delete(pendiente)
    db.session.commit()
    flash('Caso pendiente eliminado correctamente.')
    return redirect(url_for('pendientes.pendientes'))
