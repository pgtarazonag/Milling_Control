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
import pytz
VANCOUVER_TZ = pytz.timezone('America/Vancouver')

# Definimos el blueprint para las rutas de bloques
bloques_bp = Blueprint('bloques', __name__, url_prefix='/bloques')

# Ruta principal para ver, filtrar y agregar bloques
@bloques_bp.route('/', methods=['GET', 'POST'])
def bloques():
    materiales = Configuracion.get_lista('materiales', default=['Zirconia','Disilicato','PMMA','Cera','Wax','Composite'])
    shades = Configuracion.get_lista('shades', default=['A1','A2','A3','B1','B2','C1','C2'])
    marcas = Configuracion.get_lista('marcas', default=['Vita','Ivoclar','Aidite'])
    grosores = Configuracion.get_lista('grosores', default=['14','16','18','20','22','25'])
    # Cargar configuración avanzada de materiales
    import json
    try:
        materiales_avanzado = Configuracion.get_lista('materiales_avanzado')
        if not materiales_avanzado or not isinstance(materiales_avanzado, dict):
            # Si es una lista con un solo elemento JSON, decodificar
            import json
            if isinstance(materiales_avanzado, list) and len(materiales_avanzado) == 1 and (str(materiales_avanzado[0]).strip().startswith('{') or str(materiales_avanzado[0]).strip().startswith('[')):
                materiales_avanzado = json.loads(materiales_avanzado[0])
            else:
                materiales_avanzado = {}
    except Exception:
        materiales_avanzado = {}
    error = None
    # Si se envía el formulario para agregar un bloque nuevo
    if request.method == 'POST':
        material = request.form.get('material', '').strip()
        shade = request.form.get('shade', '').strip()
        grosor_str = request.form.get('grosor', '').strip()
        marca = request.form.get('marca', '').strip()
        cantidad_str = request.form.get('cantidad', '').strip()
        # Validación estricta: todos los campos obligatorios
        if not material or not shade or not grosor_str or not cantidad_str or not marca:
            error = 'Todos los campos (material, shade, grosor, marca y cantidad) son obligatorios.'
        else:
            try:
                grosor = int(grosor_str)
                cantidad = int(cantidad_str)
                from datetime import datetime
                import pytz
                VANCOUVER_TZ = pytz.timezone('America/Vancouver')
                ahora_van = datetime.now(VANCOUVER_TZ)
                # Guardar la fecha en UTC pero mostrarla en Vancouver
                nuevo = Bloque(
                    material=material,
                    marca=marca,
                    shade=shade,
                    grosor=grosor,
                    cantidad=cantidad,
                    estado='nuevo',
                    fecha_creacion=ahora_van.astimezone(pytz.utc)
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

    # Convertir fechas a Vancouver para mostrar en la tabla
    from pytz import timezone, UTC
    tz_van = timezone('America/Vancouver')
    for b in bloques_usados:
        if b.fecha_creacion:
            b.fecha_vancouver = b.fecha_creacion.replace(tzinfo=UTC).astimezone(tz_van)
        else:
            b.fecha_vancouver = None
    for b in bloques_nuevos:
        if b.fecha_creacion:
            b.fecha_vancouver = b.fecha_creacion.replace(tzinfo=UTC).astimezone(tz_van)
        else:
            b.fecha_vancouver = None

    # Renderizamos la plantilla HTML con los bloques encontrados
    return render_template(
        'bloques.html',
        materiales=materiales,
        shades=shades,
        marcas=marcas,
        grosores=grosores,
        bloques_usados=bloques_usados,
        bloques_nuevos=bloques_nuevos,
        error=error,
        materiales_avanzado=materiales_avanzado
    )

# Ruta para editar un bloque existente
@bloques_bp.route('/editar/<int:bloque_id>', methods=['GET', 'POST'])
def editar_bloque(bloque_id):
    materiales = Configuracion.get_lista('materiales', default=['Zirconia','Disilicato','PMMA','Cera','Wax','Composite'])
    marcas = Configuracion.get_lista('marcas', default=['Vita','Ivoclar','Aidite'])
    grosores = Configuracion.get_lista('grosores', default=['14','16','18','20','22','25'])
    bloque = Bloque.query.get_or_404(bloque_id)
    # Cargar configuración avanzada de materiales para shades y marcas dependientes
    import json
    try:
        materiales_avanzado = Configuracion.get_lista('materiales_avanzado')
        if isinstance(materiales_avanzado, dict):
            pass
        elif materiales_avanzado and isinstance(materiales_avanzado, list) and isinstance(materiales_avanzado[0], str) and materiales_avanzado[0].startswith('{'):
            materiales_avanzado = json.loads(materiales_avanzado[0])
        else:
            materiales_avanzado = {}
    except Exception:
        materiales_avanzado = {}
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
        shades=Configuracion.get_lista('shades', default=['A1','A2','A3','B1','B2','C1','C2']),
        materiales_avanzado=materiales_avanzado
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
        fecha_eliminacion=datetime.now(VANCOUVER_TZ)
    )
    db.session.add(historial)
    db.session.delete(bloque)
    db.session.commit()
    return redirect(url_for('bloques.bloques'))

@bloques_bp.route('/usar_bloque_nuevo/<int:bloque_id>', methods=['POST'])
def usar_bloque_nuevo(bloque_id):
    """
    Convierte un bloque nuevo en bloque usado, asignando un código único de 6 caracteres:
    2 de grosor, 1 letra de marca (o X), 3 alfanuméricos únicos.
    La fecha del bloque usado será la fecha actual.
    """
    bloque = Bloque.query.get_or_404(bloque_id)
    if bloque.estado != 'nuevo' or bloque.cantidad < 1:
        return redirect(url_for('bloques.bloques'))
    from random import choices
    import string
    from datetime import datetime
    import pytz
    VANCOUVER_TZ = pytz.timezone('America/Vancouver')
    grosor_str = str(bloque.grosor).zfill(2)
    # Obtener letra de marca desde configuración avanzada (nueva estructura)
    materiales_avanzado = Configuracion.get_lista('materiales_avanzado')
    import json
    if materiales_avanzado and isinstance(materiales_avanzado, list) and isinstance(materiales_avanzado[0], str):
        materiales_avanzado = json.loads(materiales_avanzado[0])
    letra = 'X'
    if materiales_avanzado and bloque.material in materiales_avanzado:
        marcas = materiales_avanzado[bloque.material].get('marcas', [])
        for m in marcas:
            if isinstance(m, dict) and m.get('nombre') == bloque.marca:
                letra = (m.get('letra') or 'X').upper()[:1]
                break
    usados = set(b.codigo_barra for b in Bloque.query.filter_by(estado='usado').all())
    while True:
        sufijo = ''.join(choices(string.ascii_uppercase + string.digits, k=3))
        codigo = grosor_str + letra + sufijo
        if codigo not in usados:
            break
    bloque_usado = Bloque(
        material=bloque.material,
        marca=bloque.marca,
        shade=bloque.shade,
        grosor=bloque.grosor,
        cantidad=1,
        codigo_barra=codigo,
        estado='usado',
        fecha_creacion=datetime.now(VANCOUVER_TZ)
    )
    db.session.add(bloque_usado)
    bloque.cantidad -= 1
    if bloque.cantidad <= 0:
        db.session.delete(bloque)
    db.session.commit()
    return redirect(url_for('bloques.bloques'))