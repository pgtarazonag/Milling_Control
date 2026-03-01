"""
Este archivo contiene las rutas (endpoints) relacionadas con las órdenes de fresado.

Paso a paso:
1. Se importan los módulos necesarios y los modelos de datos.
2. Se define un blueprint para organizar las rutas de órdenes.
3. Se definen funciones para generar códigos de bloque únicos.
4. Se maneja la ruta principal de órdenes, permitiendo ver, filtrar y crear nuevas órdenes.
5. Se procesa el formulario para crear una orden, asociando bloques y actualizando inventario.
6. Se actualizan los modelos fresados y la información de la fresa instalada.
7. Se muestran las órdenes existentes en una tabla.
8. Se integra la lógica para crear órdenes grupales a partir de la selección de casos pendientes.

Este archivo gestiona toda la lógica relacionada con la creación y visualización de órdenes.
"""

# Importamos los módulos necesarios y los modelos de datos
from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify
from models import Orden, Bloque, BloqueHistorial, FresaInstalada, OrdenPendiente, Configuracion, LogInventario
from extensions import db
from datetime import datetime, timedelta
import random
import string
from sqlalchemy import func, text, literal_column
import pytz

# Definimos el blueprint para las rutas de órdenes
ordenes_bp = Blueprint('ordenes', __name__, url_prefix='/ordenes')

# Zona horaria Vancouver definida globalmente
VANCOUVER_TZ = pytz.timezone('America/Vancouver')

# Tipos de material fijos para la app dental
TIPOS_MATERIAL_FIJOS = [
    "Disilicato", "Zirconia", "PMMA", "Cera", "Composite", "Resina"
]

# Función para generar un código de bloque único
# Recibe el grosor y genera un código aleatorio que no exista en la base de datos
# Se usa al crear un nuevo bloque usado

def generar_codigo_bloque(grosor, marca=None, material=None):
    grosor_str = str(grosor).zfill(2)
    letras_marca = 'XX'
    if material and marca:
        materiales_avanzado = Configuracion.get_lista('materiales_avanzado')
        import json
        if materiales_avanzado and isinstance(materiales_avanzado, list) and isinstance(materiales_avanzado[0], str):
            materiales_avanzado = json.loads(materiales_avanzado[0])
        if materiales_avanzado and material in materiales_avanzado:
            marcas = materiales_avanzado[material].get('marcas', [])
            for m in marcas:
                if isinstance(m, dict) and m.get('nombre') == marca:
                    letras_marca = (m.get('letra') or 'XX').upper()[:2].ljust(2, 'X')
                    break
    import random, string
    while True:
        sufijo = ''.join(random.choices(string.ascii_uppercase + string.digits, k=2))
        codigo = grosor_str + letras_marca + sufijo
        if len(codigo) == 6 and not Bloque.query.filter_by(codigo_barra=codigo).first():
            return codigo

# Ruta principal para ver y crear órdenes
@ordenes_bp.route('/', methods=['GET', 'POST'])
def ordenes():
    material_form = None
    shade_form = None
    error = None
    bloque = None
    maquina = None
    cantidades = []
    # Obtener todos los casos pendientes para mostrar en la interfaz de órdenes
    pendientes_orden = OrdenPendiente.query.order_by(OrdenPendiente.fecha_escaneo.asc()).all()
    # Obtenemos los filtros de material y shade desde la URL
    material = request.args.get('material')
    shade = request.args.get('shade')

    # Obtener filtros de material y shade desde POST si existen (para mantener consistencia al crear orden)
    if request.method == 'POST':
        material_post = request.form.get('material')
        shade_post = request.form.get('shade')
        maquina_post = request.form.get('maquina')
        if material_post:
            material = material_post
        if shade_post:
            shade = shade_post
        if maquina_post:
            maquina = maquina_post

    # Obtener máquinas y materiales desde configuración (asegura que estén definidas antes de cualquier render_template)
    maquinas = Configuracion.get_lista('maquinas')
    tipos_material = Configuracion.get_lista('materiales')
    # Obtenemos los tipos de material disponibles
    tipos_material_db = db.session.query(Bloque.material).distinct().all()
    tipos_material = [type[0] for type in tipos_material_db if type[0]] or tipos_material or TIPOS_MATERIAL_FIJOS
    # --- FILTRO ROBUSTO DE SHADES ---
    # Normaliza el material para evitar problemas de espacios o mayúsculas
    material_normalizado = (request.form.get('material') or request.args.get('material') or '').strip()
    if material_normalizado:
        # Busca shades para el material normalizado
        shades_disponibles = db.session.query(Bloque.shade).filter(
            db.func.lower(Bloque.material) == material_normalizado.lower()
        ).distinct().all()
        shades_disponibles = [s[0] for s in shades_disponibles if s[0]]
        # Si no hay shades, fallback: mostrar todos los shades
        if not shades_disponibles:
            shades_disponibles = [s[0] for s in db.session.query(Bloque.shade).distinct().all() if s[0]]
    else:
        shades_disponibles = [s[0] for s in db.session.query(Bloque.shade).distinct().all() if s[0]]
    # Filtrar bloques usados y nuevos según material y shade seleccionados
    bloques_usados_query = Bloque.query.filter_by(estado='usado')
    bloques_nuevos_query = Bloque.query.filter_by(estado='nuevo')
    if material_normalizado:
        bloques_usados_query = bloques_usados_query.filter(Bloque.material == material_normalizado)
        bloques_nuevos_query = bloques_nuevos_query.filter(Bloque.material == material_normalizado)
    shade_keep = request.form.get('shade') or request.args.get('shade')
    if shade_keep:
        bloques_usados_query = bloques_usados_query.filter(Bloque.shade == shade_keep)
        bloques_nuevos_query = bloques_nuevos_query.filter(Bloque.shade == shade_keep)
    bloques_usados = bloques_usados_query.all()
    bloques_nuevos = bloques_nuevos_query.all()
    # Si el usuario agrega un código pendiente desde la pestaña órdenes
    if request.method == 'POST' and 'codigo_orden_pendiente' in request.form:
        codigo_orden_pendiente = request.form.get('codigo_orden_pendiente', '').strip()
        # Guardar los valores actuales de material, shade y bloque
        material_keep = request.form.get('material') or request.args.get('material')
        shade_keep = request.form.get('shade') or request.args.get('shade')
        bloque_usado_id_keep = request.form.get('bloque_usado_id') or request.args.get('bloque_usado_id')
        bloque_nuevo_id_keep = request.form.get('bloque_nuevo_id') or request.args.get('bloque_nuevo_id')
        if codigo_orden_pendiente and not OrdenPendiente.query.filter_by(codigo_orden=codigo_orden_pendiente).first():
            nuevo = OrdenPendiente(codigo_orden=codigo_orden_pendiente)
            db.session.add(nuevo)
            db.session.commit()
            flash('Código agregado a la lista de pendientes.')
        # Redirigir con los valores actuales para mantener selección
        # --- CAMBIO: Renderizar template con POST y los valores actuales ---
        return render_template(
            'ordenes.html',
            error=None,
            pendientes_orden=OrdenPendiente.query.order_by(OrdenPendiente.fecha_escaneo.asc()).all(),
            tipos_material=tipos_material,
            material=material_keep,
            shade=shade_keep,
            maquinas=maquinas,
            shades_disponibles=shades_disponibles,
            bloques_usados=bloques_usados,
            bloques_nuevos=bloques_nuevos,
            bloque_usado_id=bloque_usado_id_keep,
            bloque_nuevo_id=bloque_nuevo_id_keep,
            ordenes=Orden.query.order_by(Orden.fecha_creacion.desc()).all(),
            request=request
        )

    # 1. Capture Form Intent and data
    is_creation = request.method == 'POST' and (request.form.get('is_creation') == '1' or 'btn_add_order' in request.form)
    codigos_seleccionados = request.form.getlist('codigos_seleccionados')

    # 2. Handle Group Order Creation (from checkboxes)
    if is_creation and codigos_seleccionados:
        material_form = request.form.get('material')
        shade_form = request.form.get('shade')
        cantidad_modelos = int(request.form.get('cantidad_modelos', 1))
        maquina = request.form.get('maquina')
        bloque_usado_id = request.form.get('bloque_usado_id')
        bloque_nuevo_id = request.form.get('bloque_nuevo_id')
        bloque = None
        if bloque_usado_id:
            bloque = Bloque.query.get(int(bloque_usado_id))
            if bloque:
                bloque.modelos_fresados += cantidad_modelos * len(codigos_seleccionados)
                codigos = bloque.get_codigos_orden_fresados()
                codigos.extend(codigos_seleccionados)
                bloque.codigos_orden_fresados = ','.join(codigos)
                # Creamos una orden para cada código seleccionado
                for codigo_orden in codigos_seleccionados:
                    nueva_orden = Orden(
                        codigos_caso=codigo_orden,
                        material=bloque.material,
                        marca=bloque.marca if hasattr(bloque, 'marca') else None,
                        shade=bloque.shade,
                        codigo_barra=bloque.codigo_barra,
                        maquina=maquina,
                        cantidad_modelos=cantidad_modelos,
                        fecha_creacion=datetime.now(VANCOUVER_TZ)
                    )
                    db.session.add(nueva_orden)
                    pendiente = OrdenPendiente.query.filter_by(codigo_orden=codigo_orden).first()
                    if pendiente:
                        db.session.delete(pendiente)
                # Actualizamos la fresa instalada solo si maquina está definida
                if maquina:
                    fresa_instalada = FresaInstalada.query.filter(
                        FresaInstalada.maquina == maquina,
                        FresaInstalada.materiales.like(f"%{bloque.material}%")
                    ).order_by(FresaInstalada.fecha_instalacion.desc()).first()
                    if fresa_instalada:
                        fresa_instalada.modelos_fresados += cantidad_modelos * len(codigos_seleccionados)
                db.session.commit()
                flash('Órdenes grupales creadas correctamente.')
                return redirect(url_for('ordenes.ordenes', material=material_form, shade=shade_form))
        elif bloque_nuevo_id:
            bloque_nuevo = Bloque.query.get(int(bloque_nuevo_id))
            if bloque_nuevo and bloque_nuevo.cantidad > 0:
                bloque_nuevo.cantidad -= 1
                # Si el bloque nuevo sigue en inventario, actualizar su fecha de creacion
                if bloque_nuevo.cantidad > 0:
                    bloque_nuevo.fecha_creacion = datetime.now(VANCOUVER_TZ)
                nuevo_bloque_usado = Bloque(
                    material=bloque_nuevo.material,
                    marca=bloque_nuevo.marca,
                    shade=bloque_nuevo.shade,
                    grosor=bloque_nuevo.grosor,
                    cantidad=1,
                    codigo_barra=generar_codigo_bloque(bloque_nuevo.grosor, bloque_nuevo.marca, bloque_nuevo.material),
                    estado='usado',
                    modelos_fresados=cantidad_modelos,
                    codigos_orden_fresados=','.join(codigos_seleccionados),
                    fecha_creacion=datetime.now(VANCOUVER_TZ)
                )
                db.session.add(nuevo_bloque_usado)
                db.session.flush()  # Para obtener el ID
                bloque = nuevo_bloque_usado
                
                # LOG
                log = LogInventario(
                    accion='CONVERSION_USADO',
                    bloque_id=bloque_nuevo.id, 
                    descripcion=f"Converted New Block to Used (Order creation). New Used Block ID: {bloque.id}, Code: {bloque.codigo_barra}",
                    detalles=json.dumps({'new_used_id': bloque.id, 'new_used_code': bloque.codigo_barra}),
                    usuario='System'
                )
                db.session.add(log)
                
                # Crear una sola orden con todos los códigos seleccionados
                nueva_orden = Orden(
                    codigos_caso=','.join(codigos_seleccionados),
                    material=bloque.material,
                    marca=bloque.marca if hasattr(bloque, 'marca') else None,
                    shade=bloque.shade,
                    codigo_barra=bloque.codigo_barra,
                    maquina=maquina,
                    cantidad_modelos=cantidad_modelos,
                    fecha_creacion=datetime.now(VANCOUVER_TZ)
                )
                db.session.add(nueva_orden)
                for codigo_orden in codigos_seleccionados:
                    pendiente = OrdenPendiente.query.filter_by(codigo_orden=codigo_orden).first()
                    if pendiente:
                        db.session.delete(pendiente)
                db.session.commit()
                # Redirigir a la pantalla de confirmación de código de bloque
                import json
                orden_data = json.dumps({
                    'codigos_seleccionados': codigos_seleccionados,
                    'maquina': maquina,
                    'cantidad_modelos': cantidad_modelos,
                    'material_form': material_form,
                    'shade_form': shade_form
                })
                return redirect(url_for('ordenes.confirmar_codigo_bloque', bloque_id=bloque.id, orden_data=orden_data))
        else: # This 'else' corresponds to the 'if bloque_usado_id' or 'elif bloque_nuevo_id'
            # If is_creation but no block selected
            error = "You must select a block (Used or New)."
            # Continue to next block instead of early return
            
    # If there was an error in the group order creation, render the template with the error
    if error:
        return render_template(
            'ordenes.html',
            error=error,
            pendientes_orden=OrdenPendiente.query.order_by(OrdenPendiente.fecha_escaneo.asc()).all(),
            tipos_material=tipos_material,
            material=material_form,
            shade=shade_form,
            maquinas=maquinas,
            shades_disponibles=shades_disponibles,
            bloques_usados=bloques_usados,
            bloques_nuevos=bloques_nuevos,
            bloque_usado_id=request.form.get('bloque_usado_id'),
            bloque_nuevo_id=request.form.get('bloque_nuevo_id'),
            maquina=maquina,
            ordenes=Orden.query.order_by(Orden.fecha_creacion.desc()).all(),
            request=request
        )
            
    # 3. Handle Single/Multiple Order Creation (from text input)
    if is_creation and not codigos_seleccionados and 'codigo_orden' in request.form:
        codigos_orden = request.form.get('codigo_orden', '').strip()
        try:
            cantidad_modelos = int(request.form.get('cantidad_modelos', 1))
        except ValueError:
            cantidad_modelos = 0
            
        material_form = request.form.get('material')
        shade_form = request.form.get('shade')
        maquina = request.form.get('maquina')
        bloque_usado_id = request.form.get('bloque_usado_id')
        bloque_nuevo_id = request.form.get('bloque_nuevo_id')
        
        # Backend Validation - Only for creation
        if not material_form or not shade_form or not maquina:
            error = "You must select Material, Shade, and Machine."
        elif not codigos_orden:
            error = "You must enter at least one Order Code."
        elif cantidad_modelos <= 0:
            error = "Number of units must be greater than zero."
            
        if not error and codigos_orden:
            codigos_lista = [c.strip() for c in codigos_orden.split(',') if c.strip()]
            
            # --- TITANIUM LOGIC ---
            is_titanium = material_form and material_form.lower() in ['titanio', 'titanium']
            if is_titanium:
                titanium_block_ids = request.form.getlist('titanium_block_ids')
                aditamento_holder = request.form.get('aditamento_holder')
                if not titanium_block_ids:
                    error = "You must select Titanium Blanks for consumption."
                else:
                    from collections import Counter
                    block_counts = Counter(titanium_block_ids)
                    consumed_refs = []
                    
                    # Verify stock availability first
                    for bid, qty_t in block_counts.items():
                        b_chk = Bloque.query.get(int(bid))
                        if not b_chk or b_chk.cantidad < qty_t:
                            error = f"Not enough quantity for block {b_chk.codigo_referencia if b_chk else bid}"
                            break
                    
                    if not error:
                        for bid, qty_t in block_counts.items():
                            bloque = Bloque.query.get(int(bid))
                            bloque.cantidad -= qty_t
                            if bloque.cantidad > 0:
                                bloque.fecha_creacion = datetime.now(VANCOUVER_TZ)
                            
                            # Log Type (shade) and real ref if it exists for the display badge
                            ref_display = f"{bloque.shade} ({bloque.codigo_referencia})" if bloque.codigo_referencia else bloque.shade
                            consumed_refs.extend([ref_display] * qty_t)
                            
                            log = LogInventario(
                                accion='CONSUMO_TITANIO',
                                bloque_id=bloque.id,
                                descripcion=f"Consumed {qty_t} units for Order {codigos_orden}",
                                usuario='System'
                            )
                            db.session.add(log)
                            
                        import json
                        nueva_orden = Orden(
                            codigos_caso=','.join(codigos_lista),
                            material=material_form,
                            marca=request.form.get('marca'),
                            shade='NA',
                            aditamento_holder=aditamento_holder,
                            codigo_barra=json.dumps(consumed_refs),
                            maquina=maquina,
                            cantidad_modelos=cantidad_modelos,
                            fecha_creacion=datetime.now(VANCOUVER_TZ)
                        )
                        db.session.add(nueva_orden)
                        
                        for codigo_orden in codigos_lista:
                            pendiente = OrdenPendiente.query.filter_by(codigo_orden=codigo_orden).first()
                            if pendiente:
                                db.session.delete(pendiente)
                                
                        if maquina:
                            fresas_compatibles = FresaInstalada.query.filter(
                                FresaInstalada.maquina == maquina,
                                FresaInstalada.materiales.like(f"%{material_form}%")
                            ).all()
                            for fresa in fresas_compatibles:
                                fresa.modelos_fresados += cantidad_modelos
                                
                        db.session.commit()
                        flash('Titanium Order created successfully.')
                        return redirect(url_for('ordenes.ordenes', material=material_form))

            bloque = None
            if not is_titanium and not error and bloque_usado_id:
                bloque = Bloque.query.get(int(bloque_usado_id))
                if bloque:
                    # Actualiza modelos_fresados del bloque (opcional: puedes sumar cantidad_modelos si quieres llevar control)
                    bloque.modelos_fresados += cantidad_modelos
                    codigos = bloque.get_codigos_orden_fresados()
                    codigos.extend(codigos_lista)
                    bloque.codigos_orden_fresados = ','.join(codigos)
                    # Crear una sola orden con todos los códigos y cantidad_modelos del form
                    nueva_orden = Orden(
                        codigos_caso=','.join(codigos_lista),
                        material=bloque.material,
                        marca=bloque.marca if hasattr(bloque, 'marca') else None,
                        shade=bloque.shade,
                        codigo_barra=bloque.codigo_barra,
                        maquina=maquina,
                        cantidad_modelos=cantidad_modelos,
                        fecha_creacion=datetime.now(VANCOUVER_TZ)
                    )
                    db.session.add(nueva_orden)
                    for codigo_orden in codigos_lista:
                        pendiente = OrdenPendiente.query.filter_by(codigo_orden=codigo_orden).first()
                        if pendiente:
                            db.session.delete(pendiente)
                    # Actualizar todas las fresas instaladas compatibles
                    if maquina:
                        fresas_compatibles = FresaInstalada.query.filter(
                            FresaInstalada.maquina == maquina,
                            FresaInstalada.materiales.like(f"%{bloque.material}%")
                        ).all()
                        for fresa in fresas_compatibles:
                            fresa.modelos_fresados += cantidad_modelos
                    db.session.commit()
                    flash('Orden creada correctamente.')
                    return redirect(url_for('ordenes.ordenes', material=material_form, shade=shade_form))
            elif not is_titanium and not error and bloque_nuevo_id:
                bloque_nuevo = Bloque.query.get(int(bloque_nuevo_id))
                if bloque_nuevo and bloque_nuevo.cantidad > 0:
                    bloque_nuevo.cantidad -= 1
                    if bloque_nuevo.cantidad > 0:
                        bloque_nuevo.fecha_creacion = datetime.now(VANCOUVER_TZ)
                    nuevo_bloque_usado = Bloque(
                        material=bloque_nuevo.material,
                        marca=bloque_nuevo.marca,
                        shade=bloque_nuevo.shade,
                        grosor=bloque_nuevo.grosor,
                        cantidad=1,
                        codigo_barra=generar_codigo_bloque(bloque_nuevo.grosor, bloque_nuevo.marca, bloque_nuevo.material),
                        estado='usado',
                        modelos_fresados=cantidad_modelos,
                        codigos_orden_fresados=','.join(codigos_lista),
                        fecha_creacion=datetime.now(VANCOUVER_TZ)
                    )
                    db.session.add(nuevo_bloque_usado)
                    bloque = nuevo_bloque_usado
                    if bloque_nuevo.cantidad == 0:
                        db.session.delete(bloque_nuevo) # Consider if we want to delete or keep w/ 0 qty (logic says delete if 0 here in this block) -- actually the logic above handles it inside checks. Wait, line 365 says delete.
                    
                    # LOG
                    log = LogInventario(
                        accion='CONVERSION_USADO',
                        bloque_id=bloque_nuevo.id, 
                        descripcion=f"Converted New Block to Used (Single Order). New Used Block ID: {bloque.id}, Code: {bloque.codigo_barra}",
                        detalles=json.dumps({'new_used_id': bloque.id, 'new_used_code': bloque.codigo_barra}),
                        usuario='System'
                    )
                    db.session.add(log)
                    
                    db.session.commit()
                    # Redirigir a la pantalla de confirmación de código de bloque
                    import json
                    orden_data = json.dumps({
                        'codigos_seleccionados': codigos_lista,
                        'maquina': maquina,
                        'cantidad_modelos': cantidad_modelos,
                        'material_form': material_form,
                        'shade_form': shade_form
                    })
                    return redirect(url_for('ordenes.confirmar_codigo_bloque', bloque_id=bloque.id, orden_data=orden_data))
                else:
                    error = "No hay bloques nuevos disponibles."
            if not is_titanium and not error and not bloque:
                error = "Debes seleccionar un bloque usado o nuevo."
            # Render template with error if needed
            if error:
                return render_template(
                    'ordenes.html',
                    error=error,
                    pendientes_orden=OrdenPendiente.query.order_by(OrdenPendiente.fecha_escaneo.asc()).all(),
                    tipos_material=tipos_material,
                    material=material_form,
                    shade=shade_form,
                    maquinas=maquinas,
                    shades_disponibles=shades_disponibles,
                    bloques_usados=bloques_usados,
                    bloques_nuevos=bloques_nuevos,
                    bloque_usado_id=bloque_usado_id,
                    bloque_nuevo_id=bloque_nuevo_id,
                    maquina=maquina,
                    ordenes=Orden.query.order_by(Orden.fecha_creacion.desc()).all(),
                    request=request
                )

    # Obtenemos todas las órdenes para mostrarlas en la tabla
    ordenes = Orden.query.order_by(Orden.fecha_creacion.desc()).all()

    # Construir shades por material para el JS
    shades_por_material = {}
    for tipo in tipos_material:
        shades = db.session.query(Bloque.shade).filter(Bloque.material == tipo).distinct().all()
        shades_por_material[tipo] = [s[0] for s in shades if s[0]]

    # Titanium Inventory
    titanium_blocks = Bloque.query.filter(
        db.or_(func.lower(Bloque.material) == 'titanio', func.lower(Bloque.material) == 'titanium'),
        Bloque.estado == 'nuevo'
    ).all()
    titanium_inventory = []
    for b in titanium_blocks:
        titanium_inventory.append({
            'id': b.id,
            'holder': b.aditamento_holder,
            'ref': b.shade, # Type is now in shade
            'real_ref': b.codigo_referencia,
            'qty': b.cantidad,
            'marca': b.marca
        })
    aditamento_holders = Configuracion.get_lista('aditamento_holders', default=['Medentica', 'DESS', 'Zimmer', 'BioHorizons'])

    # Renderizamos la plantilla HTML con los datos necesarios
    return render_template(
        'ordenes.html',
        ordenes=ordenes,
        tipos_material=tipos_material,
        shades_disponibles=shades_disponibles,
        maquinas=maquinas,
        bloques_usados=bloques_usados,
        bloques_nuevos=bloques_nuevos,
        material=material,
        shade=shade,
        maquina=maquina,
        error=error,
        pendientes_orden=pendientes_orden,
        shades_por_material=shades_por_material,
        titanium_inventory=titanium_inventory,
        aditamento_holders=aditamento_holders
    )

@ordenes_bp.route('/eliminar/<int:orden_id>', methods=['POST'])
def eliminar_orden(orden_id):
    orden = Orden.query.get_or_404(orden_id)
    db.session.delete(orden)
    db.session.commit()
    flash('Orden eliminada correctamente.')
    return redirect(url_for('ordenes.ordenes'))

@ordenes_bp.route('/eliminar_pendiente/<int:pendiente_id>', methods=['POST'])
def eliminar_pendiente(pendiente_id):
    # Eliminar el caso pendiente sin procesar lógica de órdenes ni bloques
    pendiente = OrdenPendiente.query.get(pendiente_id)
    if pendiente:
        db.session.delete(pendiente)
        db.session.commit()
        flash('Caso pendiente eliminado correctamente.')
    else:
        # Si no se encuentra por ID, intentar eliminar por código_orden (caso de inconsistencia)
        codigo = request.form.get('codigo_orden')
        if codigo:
            pendiente_alt = OrdenPendiente.query.filter_by(codigo_orden=codigo).first()
            if pendiente_alt:
                db.session.delete(pendiente_alt)
                db.session.commit()
                flash('Caso pendiente eliminado correctamente (por código).')
            else:
                flash('No se encontró el caso pendiente para eliminar.', 'danger')
        else:
            flash('No se encontró el caso pendiente para eliminar.', 'danger')
    return redirect(url_for('ordenes.ordenes'))

# Ruta para editar una orden existente
@ordenes_bp.route('/editar/<int:orden_id>', methods=['GET', 'POST'])
def editar_orden(orden_id):
    """
    Permite editar los datos de una orden existente.
    - GET: Muestra el formulario con los datos actuales.
    - POST: Guarda los cambios realizados.
    """
    orden = Orden.query.get_or_404(orden_id)
    materiales = Configuracion.get_lista('materiales')
    marcas = Configuracion.get_lista('marcas')
    shades = Configuracion.get_lista('shades')
    maquinas = Configuracion.get_lista('maquinas')
    # Obtener configuración avanzada de materiales para marcas dependientes
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
        # --- GUARDAR CAMBIOS Y AJUSTAR FRESAS INSTALADAS ---
        # Guardar valores anteriores para ajustar el conteo de fresas
        old_maquina = orden.maquina
        old_material = orden.material
        old_cantidad = orden.cantidad_modelos
        # Actualizar datos de la orden
        orden.codigos_caso = request.form['codigos_caso']
        orden.material = request.form['material']
        orden.marca = request.form['marca']
        orden.shade = request.form['shade']
        orden.maquina = request.form['maquina']
        orden.cantidad_modelos = int(request.form['cantidad_modelos'])
        # Ajustar modelos_fresados en fresas instaladas (restar a las viejas, sumar a las nuevas)
        from models import FresaInstalada
        # Restar a fresas viejas (si cambió máquina/material/cantidad)
        if old_maquina and old_material and old_cantidad:
            fresas_compatibles_antes = FresaInstalada.query.filter(
                FresaInstalada.maquina == old_maquina,
                FresaInstalada.materiales.like(f"%{old_material}%")
            ).all()
            for fresa in fresas_compatibles_antes:
                fresa.modelos_fresados = max(0, fresa.modelos_fresados - old_cantidad)
        # Sumar a fresas nuevas (si hay)
        nuevas_fresas = FresaInstalada.query.filter(
            FresaInstalada.maquina == orden.maquina,
            FresaInstalada.materiales.like(f"%{orden.material}%")
        ).all()
        for fresa in nuevas_fresas:
            fresa.modelos_fresados += orden.cantidad_modelos
        # Actualizar fecha si se edita
        if 'fecha_creacion' in request.form:
            try:
                nueva_fecha = request.form['fecha_creacion']
                if nueva_fecha:
                    from datetime import datetime
                    import pytz
                    VANCOUVER_TZ = pytz.timezone('America/Vancouver')
                    orden.fecha_creacion = VANCOUVER_TZ.localize(datetime.strptime(nueva_fecha, '%Y-%m-%dT%H:%M'))
            except Exception as e:
                pass
        db.session.commit()
        flash('Orden actualizada correctamente.')
        return redirect(url_for('ordenes.ordenes'))
    return render_template('editar_orden.html', orden=orden, materiales=materiales, marcas=marcas, shades=shades, maquinas=maquinas, materiales_avanzado=materiales_avanzado)

@ordenes_bp.route('/editar_pendiente/<int:pendiente_id>', methods=['POST'])
def editar_pendiente(pendiente_id):
    pendiente = OrdenPendiente.query.get_or_404(pendiente_id)
    nuevo_codigo = request.form.get('codigo_orden', '').strip()
    if nuevo_codigo:
        pendiente.codigo_orden = nuevo_codigo
        db.session.commit()
        flash('Caso pendiente editado correctamente.')
    else:
        flash('El código de orden no puede estar vacío.', 'danger')
    return redirect(url_for('ordenes.ordenes'))

@ordenes_bp.route('/api/graficas-inventario')
def api_graficas_inventario():
    from models import Bloque, Orden
    group = request.args.get('group', 'dia')
    fecha = request.args.get('fecha')
    if not fecha:
        ahora_van = datetime.now(VANCOUVER_TZ)
        fecha = ahora_van.strftime('%Y-%m-%d')
    bloques_shade = (
        db.session.query(Bloque.shade, func.sum(Bloque.cantidad))
        .group_by(Bloque.shade)
        .all()
    )
    result = {'bloques_shade': [{'shade': s, 'cantidad': int(c or 0)} for s, c in bloques_shade]}
    # Forzar conversión UTC -> Vancouver para la fecha de la orden
    # Esto es: fecha_creacion AT TIME ZONE 'UTC' AT TIME ZONE 'America/Vancouver'
    from sqlalchemy import text
    fecha_expr = text(f"to_char(fecha_creacion AT TIME ZONE 'UTC' AT TIME ZONE 'America/Vancouver', 'YYYY-MM-DD')")
    if group == 'dia':
        modelos = db.session.query(
            fecha_expr, func.sum(Orden.cantidad_modelos)
        ).filter(text(f"to_char(fecha_creacion AT TIME ZONE 'UTC' AT TIME ZONE 'America/Vancouver', 'YYYY-MM-DD') = :fecha")).params(fecha=fecha)
        modelos = modelos.group_by(fecha_expr).all()
        result['modelos_dia'] = [{'dia': d, 'cantidad': int(c or 0)} for d, c in modelos]
    elif group == 'maquina':
        modelos = db.session.query(
            Orden.maquina, func.sum(Orden.cantidad_modelos)
        ).filter(text(f"to_char(fecha_creacion AT TIME ZONE 'UTC' AT TIME ZONE 'America/Vancouver', 'YYYY-MM-DD') = :fecha")).params(fecha=fecha)
        modelos = modelos.group_by(Orden.maquina).all()
        result['modelos_por_maquina'] = [{'maquina': m if m else '-', 'cantidad': int(c or 0)} for m, c in modelos]
    elif group == 'material':
        modelos = db.session.query(
            Orden.material, func.sum(Orden.cantidad_modelos)
        ).filter(text(f"to_char(fecha_creacion AT TIME ZONE 'UTC' AT TIME ZONE 'America/Vancouver', 'YYYY-MM-DD') = :fecha")).params(fecha=fecha)
        modelos = modelos.group_by(Orden.material).all()
        result['modelos_por_material'] = [{'material': m if m else '-', 'cantidad': int(c or 0)} for m, c in modelos]
    elif group == 'marca':
        modelos = db.session.query(
            Orden.marca, func.sum(Orden.cantidad_modelos)
        ).filter(text(f"to_char(fecha_creacion AT TIME ZONE 'UTC' AT TIME ZONE 'America/Vancouver', 'YYYY-MM-DD') = :fecha")).params(fecha=fecha)
        modelos = modelos.group_by(Orden.marca).all()
        result['modelos_por_marca'] = [{'marca': m if m else '-', 'cantidad': int(c or 0)} for m, c in modelos]
    return jsonify(result)

@ordenes_bp.route('/api/graficas-bloques-shade')
def api_graficas_bloques_shade():
    material = request.args.get('material')
    estado = request.args.get('estado')
    order = request.args.get('order', 'cantidad_desc')
    marca = request.args.get('marca')  # Nuevo filtro de marca
    query = db.session.query(Bloque.shade, func.sum(Bloque.cantidad).label('cantidad'))
    if material:
        query = query.filter(Bloque.material == material)
    if estado:
        query = query.filter(Bloque.estado == estado)
    if marca:
        query = query.filter(Bloque.marca == marca)
    query = query.group_by(Bloque.shade)
    if order == 'alfabetico':
        query = query.order_by(Bloque.shade.asc())
    elif order == 'cantidad_asc':
        query = query.order_by(func.sum(Bloque.cantidad).asc())
    else:
        query = query.order_by(func.sum(Bloque.cantidad).desc())
    data = query.all()
    return jsonify([
        {'shade': s, 'cantidad': int(c or 0)} for s, c in data
    ])

@ordenes_bp.route('/api/cases')
def api_cases():
    from sqlalchemy import func
    tipo = request.args.get('tipo', 'ordenes')
    dias = int(request.args.get('dias', 7))
    ahora = datetime.now(VANCOUVER_TZ)
    desde = ahora - timedelta(days=dias)
    # Query base
    q = db.session.query(Orden).filter(Orden.fecha_creacion >= desde)
    # Agrupar por día
    results = {}
    for orden in q:
        fecha = orden.fecha_creacion.astimezone(VANCOUVER_TZ).strftime('%Y-%m-%d')
        if fecha not in results:
            results[fecha] = 0
        if tipo == 'ordenes':
            results[fecha] += 1
        elif tipo == 'casos':
            results[fecha] += len(orden.get_codigos_caso())
        elif tipo == 'modelos':
            results[fecha] += orden.cantidad_modelos or 0
    # Ordenar por fecha
    labels = sorted(results.keys())
    values = [results[l] for l in labels]
    label = {'ordenes': 'Órdenes', 'casos': 'Casos', 'modelos': 'Modelos'}[tipo]
    return jsonify({
        'labels': labels,
        'values': values,
        'label': label,
        'xLabel': 'Fecha'
    })

@ordenes_bp.route('/api/shades')
def api_shades():
    """
    Returns available shades for a given material
    """
    material = request.args.get('material', '').strip()
    
    if not material:
        return jsonify({'shades': []})
    
    # Query shades for the specified material
    shades = db.session.query(Bloque.shade).filter(
        db.func.lower(Bloque.material) == material.lower()
    ).distinct().all()
    
    shade_list = [s[0] for s in shades if s[0]]
    
    return jsonify({'shades': sorted(shade_list)})

@ordenes_bp.route('/api/record-cases')
def api_record_cases():
    """
    Devuelve un registro diario de casos, órdenes o modelos fresados en los últimos N días CON ACTIVIDAD.
    Parámetros GET:
      - tipo: 'casos', 'ordenes' o 'modelos'
      - dias: número de días activos hacia atrás (int)
    """
    from sqlalchemy import text, func
    tipo = request.args.get('tipo', 'casos')
    try:
        dias = int(request.args.get('dias', 5))
    except Exception:
        dias = 5
    
    # Expresión para agrupar por fecha en zona horaria Vancouver
    fecha_expr = literal_column("to_char(fecha_creacion AT TIME ZONE 'UTC' AT TIME ZONE 'America/Vancouver', 'YYYY-MM-DD')")
    
    data = []
    
    if tipo == 'casos':
        # Sumar la cantidad de códigos de caso por día
        # Primero obtenemos el número de casos por orden
        subq = db.session.query(
            Orden.id,
            func.array_length(func.string_to_array(Orden.codigos_caso, ','), 1).label('num_casos'),
            fecha_expr.label('dia')
        ).subquery()
        
        # Luego agrupamos por día, ordenamos descendente para limitar, y luego revertimos
        res = db.session.query(subq.c.dia, func.sum(subq.c.num_casos))\
            .group_by(subq.c.dia)\
            .order_by(subq.c.dia.desc())\
            .limit(dias)\
            .all()
            
        data = [{'dia': d, 'cantidad': int(c or 0)} for d, c in res]
        
    elif tipo == 'ordenes':
        res = db.session.query(
            fecha_expr.label('dia'), func.count(Orden.id)
        ).group_by(fecha_expr).order_by(fecha_expr.desc()).limit(dias).all()
        
        data = [{'dia': d, 'cantidad': int(c or 0)} for d, c in res]
        
    elif tipo == 'modelos':
        res = db.session.query(
            fecha_expr.label('dia'), func.sum(Orden.cantidad_modelos)
        ).group_by(fecha_expr).order_by(fecha_expr.desc()).limit(dias).all()
        
        data = [{'dia': d, 'cantidad': int(c or 0)} for d, c in res]
    
    # Revertir para mostrar cronológicamente (antiguo -> nuevo)
    data.reverse()
    
    return jsonify(data)

@ordenes_bp.route('/api/resumen-dia')
def api_resumen_dia():
    from datetime import datetime
    import pytz
    VANCOUVER_TZ = pytz.timezone('America/Vancouver')
    hoy = datetime.now(VANCOUVER_TZ).replace(hour=0, minute=0, second=0, microsecond=0)
    maniana = hoy.replace(hour=23, minute=59, second=59, microsecond=999999)
    ordenes = Orden.query.filter(Orden.fecha_creacion >= hoy, Orden.fecha_creacion <= maniana).all()
    num_ordenes = len(ordenes)
    num_casos = sum(len(o.get_codigos_caso()) for o in ordenes)
    num_modelos = sum(o.cantidad_modelos or 0 for o in ordenes)
    return jsonify({'ordenes': num_ordenes, 'casos': num_casos, 'modelos': num_modelos})

# Nueva ruta para confirmar/editar el código de bloque antes de crear la orden
@ordenes_bp.route('/confirmar-codigo-bloque/<int:bloque_id>', methods=['GET', 'POST'])
def confirmar_codigo_bloque(bloque_id):
    from flask import request, redirect, url_for, render_template, flash
    import json
    from datetime import datetime
    import pytz
    bloque = Bloque.query.get_or_404(bloque_id)
    orden_data = request.args.get('orden_data') or request.form.get('orden_data')
    is_ajax = request.headers.get('X-Requested-With') == 'XMLHttpRequest'
    material_form = None
    shade_form = None
    if request.method == 'POST':
        codigo_barra = request.form.get('codigo_barra', '').strip()
        if codigo_barra:
            bloque.codigo_barra = codigo_barra
            db.session.commit()
            # Recuperar datos de la orden y continuar
            if orden_data:
                try:
                    datos = json.loads(orden_data)
                except Exception:
                    datos = {}
                codigos_seleccionados = datos.get('codigos_seleccionados', [])
                maquina = datos.get('maquina')
                cantidad_modelos = datos.get('cantidad_modelos', 1)
                material_form = datos.get('material_form') or ''
                shade_form = datos.get('shade_form') or ''
                
                # Crear una ÚNICA orden con todos los códigos concatenados
                if codigos_seleccionados:
                    nueva_orden = Orden(
                        codigos_caso=','.join(codigos_seleccionados),
                        material=bloque.material,
                        marca=bloque.marca if hasattr(bloque, 'marca') else None,
                        shade=bloque.shade,
                        codigo_barra=bloque.codigo_barra,
                        maquina=maquina,
                        cantidad_modelos=cantidad_modelos,
                        fecha_creacion=datetime.now(VANCOUVER_TZ)
                    )
                    db.session.add(nueva_orden)
                    
                    # Eliminar de pendientes cada código individualmente
                    for codigo_orden in codigos_seleccionados:
                        pendiente = OrdenPendiente.query.filter_by(codigo_orden=codigo_orden).first()
                        if pendiente:
                            db.session.delete(pendiente)
                
                db.session.commit()
            # Si es AJAX, responde con un simple 'ok', si no, redirige
            if is_ajax:
                return 'ok'
            return redirect(url_for('ordenes.ordenes', material=material_form or '', shade=shade_form or ''))
    # GET: Renderiza solo el contenido del modal si es AJAX
    if is_ajax:
        return render_template('confirmar_codigo_bloque.html', bloque=bloque, orden_data=orden_data)
    # Si no es AJAX, renderiza con layout normal
    return render_template('confirmar_codigo_bloque.html', bloque=bloque, orden_data=orden_data)

# --- UNIFICACIÓN: Si hay bloque_nuevo_id, crear bloque usado y redirigir a confirmación antes de cualquier orden ---
    if request.method == 'POST':
        bloque_nuevo_id = request.form.get('bloque_nuevo_id')
        if bloque_nuevo_id:
            bloque_nuevo = Bloque.query.get(int(bloque_nuevo_id))
            if bloque_nuevo and bloque_nuevo.cantidad > 0:
                # Obtener datos de la orden
                codigos_orden = request.form.get('codigo_orden', '').strip()
                codigos_lista = [c.strip() for c in codigos_orden.split(',') if c.strip()] if codigos_orden else []
                codigos_seleccionados = request.form.getlist('codigos_seleccionados')
                if codigos_seleccionados:
                    codigos = codigos_seleccionados
                else:
                    codigos = codigos_lista
                modelos_por_caso_str = request.form.get('modelos_por_caso', '').strip()
                cantidad_modelos_total = int(request.form.get('cantidad_modelos', 1))
                if modelos_por_caso_str:
                    cantidades = []
                    for x in modelos_por_caso_str.split(','):
                        try:
                            cantidades.append(int(x.strip()))
                        except ValueError:
                            cantidades.append(None)
                    faltantes = [i for i, v in enumerate(cantidades) if not v]
                    if faltantes:
                        suma_definidos = sum([v for v in cantidades if v])
                        restantes = max(cantidad_modelos_total - suma_definidos, 0)
                        base = restantes // len(faltantes) if faltantes else 0
                        resto = restantes % len(faltantes) if faltantes else 0
                        for idx, i in enumerate(faltantes):
                            cantidades[i] = base + (1 if idx < resto else 0)
                if len(cantidades) != len(codigos):
                    base = cantidad_modelos_total // len(codigos)
                    resto = cantidad_modelos_total % len(codigos)
                    cantidades = [base + 1 if i < resto else base for i in range(len(codigos))]
                cantidad_modelos = sum(cantidades)
                bloque_nuevo.cantidad -= 1
                # Si el bloque nuevo sigue en inventario, actualizar su fecha de creacion
                if bloque_nuevo.cantidad > 0:
                    bloque_nuevo.fecha_creacion = datetime.now(VANCOUVER_TZ)
                nuevo_bloque_usado = Bloque(
                    material=bloque_nuevo.material,
                    marca=bloque_nuevo.marca,
                    shade=bloque_nuevo.shade,
                    grosor=bloque_nuevo.grosor,
                    cantidad=1,
                    codigo_barra=generar_codigo_bloque(bloque_nuevo.grosor, bloque_nuevo.marca, bloque_nuevo.material),
                    estado='usado',
                    modelos_fresados=cantidad_modelos,
                    codigos_orden_fresados=','.join(codigos),
                    fecha_creacion=datetime.now(VANCOUVER_TZ)
                )
                db.session.add(nuevo_bloque_usado)
                db.session.flush()
                if bloque_nuevo.cantidad == 0:
                    db.session.delete(bloque_nuevo)
                db.session.commit()
                # En vez de redirigir, devolver JSON para el modal
                return jsonify({
                    'status': 'ok',
                    'bloque_usado': {
                        'id': bloque.id,
                        'codigo_barra': bloque.codigo_barra,
                        'material': bloque.material,
                        'marca': bloque.marca,
                        'shade': bloque.shade,
                        'grosor': bloque.grosor
                    }
                })

@ordenes_bp.route('/api/analytics/shade-distribution')
def api_analytics_shade_distribution():
    """
    Returns shade distribution based on:
    - 'orders': count of orders
    - 'cases': count of individual cases (split by comma)
    - 'units': sum of units (cantidad_modelos)
    """
    metric = request.args.get('metric', 'units')  # units, cases, orders
    material = request.args.get('material')
    limit_arg = request.args.get('limit')
    
    query = db.session.query(Orden)
    
    if material:
        query = query.filter(Orden.material == material)
        
    if limit_arg and limit_arg != 'total':
        try:
            limit_days = int(limit_arg)
            # Find the last N distinct dates (days)
            # This is complex in pure ORM for SQLite/Postgres compatibility without raw SQL, 
            # but we can do a subquery or 2 steps.
            # Step 1: Get distinct valid dates descending
            from sqlalchemy import func
            # We use the date part of fecha_creacion
            # Note: We need to handle timezone if strictly required, but for "active days" 
            # sorting by fecha_creacion desc is usually sufficient to find cutoffs.
            
            # Efficient way: Get all dates, distinct, sort, pick Nth.
            # Since dataset is likely not massive, fetching distinct dates is okay. 
            # For massive datasets, this needs optimization.
            
            # Using simple python-side unique date extraction for simplicity and DB-agnostic behavior 
            # (unless dataset is huge, which it doesn't seem to be yet).
            # ACTUALLY, let's do a proper query to get distinct dates.
            # Using strftime for SQLite/Postgres generic approach if possible, but distinct(date(fecha_creacion)) is safer.
            
            # Let's try to filter by range. 
            # First, find the distinct dates available
            available_dates = db.session.query(func.date(Orden.fecha_creacion)).distinct().order_by(func.date(Orden.fecha_creacion).desc()).limit(limit_days).all()
            
            if available_dates:
                # available_dates is a list of tuples like [('2023-10-20',), ('2023-10-18',)]
                # Logic: Filter orders where date(fecha_creacion) >= smallest_date found
                oldest_date_str = available_dates[-1][0]
                query = query.filter(func.date(Orden.fecha_creacion) >= oldest_date_str)
                
        except ValueError:
            pass # Ignore invalid limit
    
    # Calculate totals by shade
    # We fetch all and process in python for 'cases' splitting simplicity, 
    # unless we want to use complex SQL array functions. Given the scale, Python processing is fine.
    ordenes = query.all()
    
    distribution = {}
    
    for orden in ordenes:
        shade = orden.shade or 'Unknown'
        if shade not in distribution:
            distribution[shade] = 0
            
        if metric == 'orders':
            distribution[shade] += 1
        elif metric == 'units':
            distribution[shade] += (orden.cantidad_modelos or 0)
        elif metric == 'cases':
            count = len(orden.get_codigos_caso())
            distribution[shade] += count

    # Sort by value desc
    sorted_dist = sorted(distribution.items(), key=lambda x: x[1], reverse=True)

    # NEW: Fetch inventory counts (Total Blocks) for the relevant material/shades
    # We query Bloque table where estado='nuevo' (lowercase, based on routes/bloques.py)
    # We MUST SUM(Bloque.cantidad) because one row can represent multiple blocks.
    
    from models import Bloque
    
    inventory_query = db.session.query(Bloque.shade, func.sum(Bloque.cantidad))\
        .filter(Bloque.estado == 'nuevo')
        
    if material:
        inventory_query = inventory_query.filter(Bloque.material == material)
        
    inventory_counts_list = inventory_query.group_by(Bloque.shade).all()
    # inventory_counts_list is list of (shade, total_qty)
    # Convert to dict for easy lookup: {'A1': 5, 'B2': 0}
    inventory_map = {shade: (qty or 0) for shade, qty in inventory_counts_list}
    
    # Construct inventory list matching the sorted_dist order
    # sorted_dist is [('A1', 50), ('B2', 20)]
    inventory_values = []
    
    for shade, _ in sorted_dist:
        # Use existing map or 0
        inv_count = inventory_map.get(shade, 0)
        inventory_values.append(inv_count)
    
    return jsonify({
        'labels': [k for k, v in sorted_dist],
        'values': [v for k, v in sorted_dist],
        'inventory': inventory_values
    })