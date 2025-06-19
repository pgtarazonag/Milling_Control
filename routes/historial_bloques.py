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
from flask import Blueprint, render_template
# Importamos el modelo que representa el historial de bloques en la base de datos
from models import BloqueHistorial

# Creamos un blueprint llamado 'historial' para agrupar las rutas relacionadas con el historial
historial_bp = Blueprint('historial', __name__, url_prefix='/historial')

# Definimos la ruta '/bloques' dentro del blueprint
@historial_bp.route('/bloques')
def historial_bloques():
    # Consultamos todos los registros del historial de bloques, ordenados por fecha de eliminación descendente
    historial = BloqueHistorial.query.order_by(BloqueHistorial.fecha_eliminacion.desc()).all()
    # Renderizamos la plantilla HTML y le pasamos la lista de bloques del historial
    return render_template('historial_bloques.html', historial=historial)