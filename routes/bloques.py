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
from flask import Blueprint, render_template, request, redirect, url_for, flash
from models import Bloque, BloqueHistorial, Configuracion, LogInventario
from extensions import db
from datetime import datetime
import pytz
import json
VANCOUVER_TZ = pytz.timezone('America/Vancouver')

# Definimos el blueprint para las rutas de bloques
bloques_bp = Blueprint('bloques', __name__, url_prefix='/bloques')
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

    # Mapa de referencias existentes: {(Material, Marca, Shade, Grosor): RefCode}
    # Solo bloques nuevos que tengan código de referencia
    bloques_ref = Bloque.query.filter(
        Bloque.estado == 'nuevo', 
        Bloque.codigo_referencia != None, 
        Bloque.codigo_referencia != ''
    ).all()
    mapa_referencias = {}
    for b in bloques_ref:
        # Clave compuesta para identificar el tipo de bloque
        # Asegurar tipos string/int consistentes
        key = f"{b.material}|{b.marca}|{b.shade}|{b.grosor}"
        mapa_referencias[key] = b.codigo_referencia
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
                codigo_referencia = request.form.get('codigo_referencia', '').strip()
                from datetime import datetime
                import pytz
                VANCOUVER_TZ = pytz.timezone('America/Vancouver')
                ahora_van = datetime.now(VANCOUVER_TZ)
                # Upsert: si ya existe un bloque "nuevo" con mismas características, sumar cantidad
                existente = (
                    Bloque.query
                    .filter_by(estado='nuevo', material=material, marca=marca, shade=shade, grosor=grosor, codigo_barra=None)
                    .first()
                )
                if existente:
                    # Update reference code if provided
                    old_qty = existente.cantidad
                    if codigo_referencia:
                        existente.codigo_referencia = codigo_referencia
                    existente.cantidad = (existente.cantidad or 0) + cantidad
                    # Guardar la fecha en UTC para consistencia con la vista
                    try:
                        import pytz as _p
                        existente.fecha_creacion = ahora_van.astimezone(_p.utc)
                    except Exception:
                        existente.fecha_creacion = ahora_van
                    
                    # LOG
                    log = LogInventario(
                        accion='ALTA_INCREMENTO',
                        bloque_id=existente.id,
                        descripcion=f"Quantity increased (+{cantidad}) for: {material} {shade} {grosor}mm",
                        detalles=json.dumps({
                            'old_qty': old_qty, 
                            'new_qty': existente.cantidad, 
                            'added': cantidad,
                            'material': material,
                            'shade': shade,
                            'marca': marca,
                            'grosor': grosor
                        }),
                        usuario='System'
                    )
                    db.session.add(log)
                    db.session.commit()
                else:
                    # Guardar la fecha en UTC pero mostrarla en Vancouver
                    nuevo = Bloque(
                        material=material,
                        marca=marca,
                        shade=shade,
                        grosor=grosor,
                        cantidad=cantidad,
                        codigo_referencia=codigo_referencia,
                        estado='nuevo',
                        fecha_creacion=ahora_van.astimezone(pytz.utc)
                    )
                    db.session.add(nuevo)
                    db.session.commit() # Commit first to get ID
                    
                    # LOG
                    log = LogInventario(
                        accion='ALTA_NUEVO',
                        bloque_id=nuevo.id,
                        descripcion=f"New block added: {material} {shade} {grosor}mm (Qty: {cantidad})",
                        detalles=json.dumps({
                            'material': material, 
                            'shade': shade, 
                            'grosor': grosor, 
                            'cantidad': cantidad,
                            'marca': marca
                        }),
                        usuario='System'
                    )
                    db.session.add(log)
                    db.session.commit()
                    if codigo_referencia:
                        existente.codigo_referencia = codigo_referencia
                    existente.cantidad = (existente.cantidad or 0) + cantidad
                    # Guardar la fecha en UTC para consistencia con la vista
                    try:
                        import pytz as _p
                        existente.fecha_creacion = ahora_van.astimezone(_p.utc)
                    except Exception:
                        existente.fecha_creacion = ahora_van
                    
                    # LOG
                    log = LogInventario(
                        accion='ALTA_INCREMENTO',
                        bloque_id=existente.id,
                        descripcion=f"Increased quantity for existing new block type: {material} {shade} {grosor}mm. ({old_qty} -> {existente.cantidad})",
                        detalles=json.dumps({'old_qty': old_qty, 'new_qty': existente.cantidad, 'added': cantidad}),
                        usuario='System'
                    )
                    db.session.add(log)
                    db.session.commit()
                return redirect(url_for('bloques.bloques'))
            except ValueError:
                error = 'El grosor y la cantidad deben ser números válidos.'

    # Filtros GET para buscar bloques por material, shade o estado
    material = request.args.get('material')
    shade = request.args.get('shade')
    estado = request.args.get('estado')
    mostrar_ceros = request.args.get('mostrar_ceros') == '1'

    # Consultas para obtener bloques usados y nuevos según los filtros
    query_usados = Bloque.query.filter_by(estado='usado')
    query_nuevos = Bloque.query.filter_by(estado='nuevo')
    
    if not mostrar_ceros:
        query_nuevos = query_nuevos.filter(Bloque.cantidad > 0)

    if material:
        query_usados = query_usados.filter_by(material=material)
        query_nuevos = query_nuevos.filter_by(material=material)
    if shade:
        query_usados = query_usados.filter_by(shade=shade)
        query_nuevos = query_nuevos.filter_by(shade=shade)

    if estado == 'usado':
        bloques_usados = query_usados.order_by(Bloque.fecha_creacion.desc()).all()
        bloques_nuevos = []
    elif estado == 'nuevo':
        bloques_usados = []
        bloques_nuevos = query_nuevos.order_by(Bloque.fecha_creacion.desc()).all()
    else:
        bloques_usados = query_usados.order_by(Bloque.fecha_creacion.desc()).all()
        bloques_nuevos = query_nuevos.order_by(Bloque.fecha_creacion.desc()).all()

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
        materiales_avanzado=materiales_avanzado,
        mapa_referencias=mapa_referencias # DATA FOR JS
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
        bloque.marca = request.form.get('marca')  # Siempre guardar marca
        # Solo actualizar cantidad si el bloque es nuevo y el campo existe en el form
        if bloque.estado == 'nuevo' and 'cantidad' in request.form:
            bloque.cantidad = int(request.form['cantidad'])
        bloque.estado = request.form['estado']
        bloque.codigo_referencia = request.form.get('codigo_referencia')
        bloque.codigo_barra = request.form.get('codigo_barra') if bloque.estado == 'usado' else None
        bloque.modelos_fresados = int(request.form.get('modelos_fresados', bloque.modelos_fresados or 0))
        # Si editas los códigos de orden fresados, actualízalos aquí
        codigos_orden = request.form.get('codigos_orden_fresados')
        if codigos_orden is not None:
            bloque.codigos_orden_fresados = codigos_orden
        # Actualizar la fecha de edición
        from datetime import datetime
        import pytz
        VANCOUVER_TZ = pytz.timezone('America/Vancouver')
        bloque.fecha_creacion = datetime.now(VANCOUVER_TZ)
        
        # LOG
        detalles_json = json.dumps({
            'material': request.form['material'],
            'shade': request.form['shade'],
            'grosor': int(request.form['grosor']),
            'marca': request.form.get('marca')
        })
        log = LogInventario(
            accion='EDICION',
            bloque_id=bloque.id,
            descripcion=f"Block edited {bloque.id}: {request.form['material']} {request.form['shade']}",
            detalles=detalles_json,
            usuario='System'
        )
        db.session.add(log)
        
        db.session.commit()
        return redirect(url_for('bloques.bloques'))

    # Asegura que la marca del bloque esté en la lista de marcas para cualquier material
    if bloque.marca and bloque.marca not in marcas and bloque.marca.strip():
        marcas = list(marcas) + [bloque.marca]

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
        codigo_referencia=bloque.codigo_referencia,
        estado=bloque.estado,
        modelos_fresados=bloque.modelos_fresados,
        codigos_orden_fresados=bloque.codigos_orden_fresados,
        fecha_creacion=bloque.fecha_creacion,
        fecha_eliminacion=datetime.now(VANCOUVER_TZ)
    )
    db.session.add(historial)
    
    # LOG
    log = LogInventario(
        accion='ELIMINACION',
        bloque_id=bloque.id,
        descripcion=f"Block deleted (Archived): {bloque.material} {bloque.shade} (ID: {bloque.id})",
        detalles=json.dumps({
            'material': bloque.material,
            'shade': bloque.shade,
            'marca': bloque.marca,
            'grosor': bloque.grosor,
            'cantidad': bloque.cantidad,
            'codigo_barra': bloque.codigo_barra
        }),
        usuario='System'
    )
    db.session.add(log)
    
    db.session.delete(bloque)
    db.session.commit()
    return redirect(url_for('bloques.bloques'))

@bloques_bp.route('/usar_bloque_nuevo/<int:bloque_id>', methods=['POST'])
def usar_bloque_nuevo(bloque_id):
    """
    Convierte un bloque nuevo en bloque usado, asignando un código único de 6 caracteres:
    2 de grosor, 2 letras de marca, 2 alfanuméricos únicos.
    La fecha del bloque usado será la fecha actual.
    """
    from flask import request, redirect, url_for
    import json
    bloque = Bloque.query.get_or_404(bloque_id)
    if bloque.estado != 'nuevo' or bloque.cantidad < 1:
        return redirect(url_for('bloques.bloques'))
    from random import choices
    import string
    from datetime import datetime
    import pytz
    VANCOUVER_TZ = pytz.timezone('America/Vancouver')
    # Permitir código personalizado desde el formulario
    codigo = request.form.get('codigo')
    usados = set(b.codigo_barra for b in Bloque.query.filter_by(estado='usado').all())
    if not codigo or codigo in usados:
        grosor_str = str(bloque.grosor).zfill(2)
        materiales_avanzado = Configuracion.get_lista('materiales_avanzado')
        if materiales_avanzado and isinstance(materiales_avanzado, list) and isinstance(materiales_avanzado[0], str):
            materiales_avanzado = json.loads(materiales_avanzado[0])
        letra = 'XX'
        if materiales_avanzado and bloque.material in materiales_avanzado:
            marcas = materiales_avanzado[bloque.material].get('marcas', [])
            for m in marcas:
                if isinstance(m, dict) and m.get('nombre') == bloque.marca:
                    letra = (m.get('letra') or 'XX').upper()[:2].ljust(2, 'X')
                    break
        while True:
            sufijo = ''.join(choices(string.ascii_uppercase + string.digits, k=2))
            codigo = grosor_str + letra + sufijo
            if codigo not in usados:
                break
    bloque_usado = Bloque(
        material=bloque.material,
        marca=bloque.marca,
        shade=bloque.shade,
        grosor=bloque.grosor,
        codigo_referencia=bloque.codigo_referencia,
        cantidad=1,
        codigo_barra=codigo,
        estado='usado',
        fecha_creacion=datetime.now(VANCOUVER_TZ)
    )
    db.session.add(bloque_usado)
    bloque.cantidad -= 1
    # ACTUALIZAR FECHA DE CREACIÓN DEL BLOQUE NUEVO SI SIGUE EN INVENTARIO
    if bloque.cantidad > 0:
        bloque.fecha_creacion = datetime.now(VANCOUVER_TZ)
    # else: bloque.cantidad is 0, keep it (do not delete) for reference
    db.session.commit() # Commit to get ID
    
    # LOG
    log = LogInventario(
        accion='CONVERSION_USADO',
        bloque_id=bloque.id, # Link to original New block
        descripcion=f"Converted New to Used. Used Block ID: {bloque_usado.id}, Code: {bloque_usado.codigo_barra}",
        detalles=json.dumps({
            'material': bloque.material,
            'shade': bloque.shade,
            'marca': bloque.marca,
            'grosor': bloque.grosor,
            'new_used_id': bloque_usado.id, 
            'new_used_code': bloque_usado.codigo_barra
        }),
        usuario='System'
    )
    db.session.add(log)
    db.session.commit()
    # Antes: Redirigir a la pantalla de confirmación de código de bloque (sin orden_data)
    # return redirect(url_for('ordenes.confirmar_codigo_bloque', bloque_id=bloque_usado.id))
    # Ahora: Redirigir directamente a la lista de bloques
    return redirect(url_for('bloques.bloques'))

@bloques_bp.route('/api/generar-codigo-usado')
def api_generar_codigo_usado():
    """
    API para sugerir un código de bloque usado, dado un bloque_id.
    """
    from flask import request, jsonify
    bloque_id = request.args.get('bloque_id', type=int)
    bloque = Bloque.query.get_or_404(bloque_id)
    from random import choices
    import string
    import pytz
    VANCOUVER_TZ = pytz.timezone('America/Vancouver')
    grosor_str = str(bloque.grosor).zfill(2)
    materiales_avanzado = Configuracion.get_lista('materiales_avanzado')
    import json
    if materiales_avanzado and isinstance(materiales_avanzado, list) and isinstance(materiales_avanzado[0], str):
        materiales_avanzado = json.loads(materiales_avanzado[0])
    letra = 'XX'
    if materiales_avanzado and bloque.material in materiales_avanzado:
        marcas = materiales_avanzado[bloque.material].get('marcas', [])
        for m in marcas:
            if isinstance(m, dict) and m.get('nombre') == bloque.marca:
                letra = (m.get('letra') or 'XX').upper()[:2].ljust(2, 'X')
                break
    usados = set(b.codigo_barra for b in Bloque.query.filter_by(estado='usado').all())
    while True:
        sufijo = ''.join(choices(string.ascii_uppercase + string.digits, k=2))
        codigo = grosor_str + letra + sufijo
        if codigo not in usados:
            break
    return jsonify({'codigo': codigo})

@bloques_bp.route('/modificar_cantidad/<int:bloque_id>', methods=['POST'])
def modificar_cantidad(bloque_id):
    from flask import request, redirect, url_for, flash
    bloque = Bloque.query.get_or_404(bloque_id)
    accion = request.form.get('accion')
    if accion == '+1':
        bloque.cantidad += 1
        # Actualizar la fecha de edición
        from datetime import datetime
        import pytz
        VANCOUVER_TZ = pytz.timezone('America/Vancouver')
        bloque.fecha_creacion = datetime.now(VANCOUVER_TZ)
        bloque.fecha_creacion = datetime.now(VANCOUVER_TZ)
        
        # LOG
        # LOG
        log = LogInventario(
            accion='AJUSTE_CANTIDAD',
            bloque_id=bloque.id,
            descripcion=f"Quantity increased (+1) for block {bloque.id}. New Qty: {bloque.cantidad}",
            detalles=json.dumps({
                'material': bloque.material,
                'shade': bloque.shade,
                'marca': bloque.marca,
                'grosor': bloque.grosor,
                'new_qty': bloque.cantidad
            }),
            usuario='System'
        )
        db.session.add(log)
        
        db.session.commit()
        flash('Cantidad aumentada.', 'success')
    elif accion == '-1' and bloque.cantidad > 1:
        bloque.cantidad -= 1
        # Actualizar la fecha de edición
        from datetime import datetime
        import pytz
        VANCOUVER_TZ = pytz.timezone('America/Vancouver')
        bloque.fecha_creacion = datetime.now(VANCOUVER_TZ)
        bloque.fecha_creacion = datetime.now(VANCOUVER_TZ)
        
        # LOG
        # LOG
        log = LogInventario(
            accion='AJUSTE_CANTIDAD',
            bloque_id=bloque.id,
            descripcion=f"Quantity decreased (-1) for block {bloque.id}. New Qty: {bloque.cantidad}",
            detalles=json.dumps({
                'material': bloque.material,
                'shade': bloque.shade,
                'marca': bloque.marca,
                'grosor': bloque.grosor,
                'new_qty': bloque.cantidad
            }),
            usuario='System'
        )
        db.session.add(log)
        
        db.session.commit()
        flash('Cantidad reducida.', 'success')
    else:
        flash('No se puede reducir más.', 'warning')
    return redirect(url_for('bloques.bloques'))

@bloques_bp.route('/eliminar_usado/<int:bloque_id>', methods=['POST'])
def eliminar_bloque_usado(bloque_id):
    """
    Elimina un bloque usado. 
    Si 'permanente' está en form/args, borra sin historial.
    De lo contrario, mueve al historial antes de borrar.
    """
    bloque = Bloque.query.get_or_404(bloque_id)
    if bloque.estado != 'usado':
        flash('Solo se pueden eliminar bloques usados.', 'warning')
        return redirect(url_for('historial.historial_bloques'))
    
    permanente = request.form.get('permanente') == '1' or request.args.get('permanente') == '1'

    if not permanente:
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
        msg = 'Bloque usado eliminado correctamente (archivado en historial).'
    else:
        msg = 'Bloque usado eliminado permanentemente.'

    # LOG
    tipo_elim = 'Permanente' if permanente else 'Archivado'
    log = LogInventario(
        accion=f'ELIMINACION_USADO_{tipo_elim.upper()}',
        bloque_id=bloque.id,
        descripcion=f"Deleted Used Block ({tipo_elim}): {bloque.codigo_barra} ({bloque.material} {bloque.shade})",
        detalles=json.dumps({
            'material': bloque.material,
            'shade': bloque.shade,
            'marca': bloque.marca,
            'grosor': bloque.grosor,
            'codigo_barra': bloque.codigo_barra,
            'tipo_eliminacion': tipo_elim
        }),
        usuario='System'
    )
    db.session.add(log)

    db.session.delete(bloque)
    db.session.commit()
    flash(msg, 'success')
    return redirect(url_for('bloques.bloques'))

@bloques_bp.route('/eliminar_varios_usados', methods=['POST'])
def eliminar_varios_bloques_usados():
    """
    Elimina varios bloques usados seleccionados, moviéndolos al historial antes de borrar.
    """
    ids = request.form.getlist('bloques_ids')
    count = 0
    for bloque_id in ids:
        bloque = Bloque.query.get(bloque_id)
        if bloque and bloque.estado == 'usado':
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
            
            # LOG
            log = LogInventario(
                accion='ELIMINACION_MASIVA',
                bloque_id=bloque.id,
                descripcion=f"Mass Delete (Archived): {bloque.codigo_barra}",
                detalles=json.dumps({
                    'material': bloque.material,
                    'shade': bloque.shade,
                    'marca': bloque.marca,
                    'grosor': bloque.grosor,
                    'codigo_barra': bloque.codigo_barra
                }),
                usuario='System'
            )
            db.session.add(log)
            
            db.session.delete(bloque)
            count += 1
    db.session.commit()
    flash(f'Se eliminaron {count} bloques usados.', 'success')
    return redirect(url_for('historial.historial_bloques'))

@bloques_bp.route('/api/stock-shade-grosor')
def api_stock_shade_grosor():
    """Devuelve el stock de bloques nuevos agrupado por shade y grosor.
    Respuesta: {
      "shades": ["A1","A2",...],
      "grosores": [14,16,...],
      "matriz": [[qty_por_grosor_para_shade_0], [para_shade_1], ...]
    }
    """
    from flask import jsonify, request
    # Filtrar opcionalmente por material (p.ej. material=Zirconia)
    material = request.args.get('material')
    if material:
        bloques = Bloque.query.filter_by(estado='nuevo', material=material).all()
    else:
        # Obtener todos los bloques nuevos
        bloques = Bloque.query.filter_by(estado='nuevo').all()
    # Agregar por (shade, grosor)
    shades = set()
    grosores = set()
    agg = {}
    for b in bloques:
        if not b.shade or b.grosor is None:
            continue
        shades.add(b.shade)
        grosores.add(int(b.grosor))
        key = (b.shade, int(b.grosor))
        agg[key] = agg.get(key, 0) + (b.cantidad or 0)
    shades = sorted(shades)
    grosores = sorted(grosores)
    # Construir matriz [len(shades) x len(grosores)]
    matriz = []
    for s in shades:
        fila = []
        for g in grosores:
            fila.append(agg.get((s, g), 0))
        matriz.append(fila)
    return jsonify({
        'shades': shades,
        'grosores': grosores,
        'matriz': matriz
    })

@bloques_bp.route('/api/vida-bloques')
def api_vida_bloques():
    """Calcula vida útil en semanas por shade usando historial (fecha_eliminacion - fecha_creacion).
    Respuesta: { labels: [shades], values: [avg_weeks], counts: [n] }
    """
    from flask import jsonify
    import pytz as _p
    registros = BloqueHistorial.query.filter(
        BloqueHistorial.fecha_creacion.isnot(None),
        BloqueHistorial.fecha_eliminacion.isnot(None)
    ).all()
    por_shade = {}
    def to_utc(dt):
        try:
            if dt is None:
                return None
            if dt.tzinfo is None:
                # asumir UTC si es naive
                return dt.replace(tzinfo=_p.UTC)
            return dt.astimezone(_p.UTC)
        except Exception:
            return dt
    for r in registros:
        if not r.shade:
            continue
        fc = to_utc(r.fecha_creacion)
        fe = to_utc(r.fecha_eliminacion)
        try:
            delta = (fe - fc).total_seconds()
            semanas = max(delta / (7 * 24 * 3600), 0)
        except Exception:
            continue
        arr = por_shade.setdefault(r.shade, [])
        arr.append(semanas)
    labels = []
    values = []
    counts = []
    items = []
    for shade, lst in por_shade.items():
        if not lst:
            continue
        avg = sum(lst) / len(lst)
        items.append((shade, avg, len(lst)))
    items.sort(key=lambda x: x[1], reverse=True)
    for shade, avg, n in items:
        labels.append(shade)
        values.append(round(avg, 2))
        counts.append(n)
    return jsonify({'labels': labels, 'values': values, 'counts': counts})

@bloques_bp.route('/api/audit-log')
def api_audit_log():
    """Devuelve el log de auditoría en formato JSON para DataTables"""
    from models import LogInventario
    from flask import jsonify
    import pytz as _p
    
    logs = LogInventario.query.order_by(LogInventario.fecha.desc()).limit(500).all() # Limit 500 for safety, add pagination later if needed
    
    data = []
    tz_van = _p.timezone('America/Vancouver')
    
    for log in logs:
        fecha_str = ''
        if log.fecha:
            # Convert UTC/Naive to Vancouver
            dt = log.fecha
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=_p.UTC)
            dt_van = dt.astimezone(tz_van)
            fecha_str = dt_van.strftime('%Y-%m-%d %H:%M')
        
        # Parse details to extract material/shade/brand/thickness
        detalles = {}
        if log.detalles:
            try:
                import json
                detalles = json.loads(log.detalles)
            except:
                detalles = {}
            
        data.append({
            'id': log.id,
            'fecha': fecha_str,
            'accion': log.accion,
            'descripcion': log.descripcion,
            'usuario': log.usuario,
            'material': detalles.get('material', ''),
            'shade': detalles.get('shade', ''),
            'marca': detalles.get('marca', ''),
            'grosor': detalles.get('grosor', '')
        })
        
    return jsonify({'data': data})

@bloques_bp.route('/api/audit-log/eliminar/<int:log_id>', methods=['POST'])
def eliminar_log(log_id):
    from models import LogInventario
    log = LogInventario.query.get_or_404(log_id)
    db.session.delete(log)
    db.session.commit()
    return jsonify({'success': True, 'message': 'Registro eliminado'})

@bloques_bp.route('/api/audit-log/editar/<int:log_id>', methods=['POST'])
def editar_log(log_id):
    from models import LogInventario
    log = LogInventario.query.get_or_404(log_id)
    nueva_desc = request.form.get('descripcion')
    if nueva_desc:
        log.descripcion = nueva_desc
        db.session.commit()
        return jsonify({'success': True, 'message': 'Registro actualizado'})
    return jsonify({'success': False, 'message': 'Descripción vacía'}), 400