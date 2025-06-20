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
from flask import Blueprint, render_template, send_file, request
# Importamos el modelo que representa el historial de bloques en la base de datos
from models import BloqueHistorial, Orden, Bloque, FresaInventario, FresaInstalada, Mantenimiento, OrdenPendiente
from extensions import db
import io
import pandas as pd

# Creamos un blueprint llamado 'historial' para agrupar las rutas relacionadas con el historial
historial_bp = Blueprint('historial', __name__, url_prefix='/historial')

# Definimos la ruta '/bloques' dentro del blueprint
@historial_bp.route('/bloques')
def historial_bloques():
    # Consultamos todos los registros del historial de bloques, ordenados por fecha de eliminación descendente
    historial = BloqueHistorial.query.order_by(BloqueHistorial.fecha_eliminacion.desc()).all()
    # Renderizamos la plantilla HTML y le pasamos la lista de bloques del historial
    return render_template('historial_bloques.html', historial=historial)

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
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
        for nombre, modelo in tablas.items():
            if nombre in seleccionadas:
                df = pd.read_sql(modelo.query.statement, db.session.bind)
                df.to_excel(writer, sheet_name=nombre, index=False)
    output.seek(0)
    return send_file(output, as_attachment=True, download_name='historial_fresado.xlsx', mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')