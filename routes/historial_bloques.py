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
from models import BloqueHistorial, Orden, Bloque, FresaInventario, FresaInstalada, Mantenimiento, OrdenPendiente
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
    return render_template('historial_bloques.html', bloques_historial=bloques_historial, bloques_usados_ordenados=bloques_usados_ordenados)

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
                except Exception:
                    cols = [c.name for c in modelo.__table__.columns]
                    df = pd.DataFrame(columns=cols)
                # Escribir hoja
                safe_sheet = nombre[:31]
                df.to_excel(writer, sheet_name=safe_sheet, index=False)
                # Ajustes de ancho
                try:
                    worksheet = writer.sheets[safe_sheet]
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
        download_name=f"historial_fresado_{datetime.now(VANCOUVER_TZ).strftime('%Y%m%d_%H%M')}.xlsx",
        mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
    )