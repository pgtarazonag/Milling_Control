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
from models import Orden, Bloque, BloqueHistorial, FresaInstalada, OrdenPendiente, Configuracion
from extensions import db
from datetime import datetime
import random
import string
from sqlalchemy import func, text

# Tipos de material fijos para la app dental
TIPOS_MATERIAL_FIJOS = [
    "Disilicato", "Zirconia", "PMMA", "Cera", "Composite", "Resina"
]

# Definimos el blueprint para las rutas de órdenes
ordenes_bp = Blueprint('ordenes', __name__, url_prefix='/ordenes')

# Función para generar un código de bloque único
# Recibe el grosor y genera un código aleatorio que no exista en la base de datos
# Se usa al crear un nuevo bloque usado

def generar_codigo_bloque(grosor):
    # 2 dígitos para grosor (rellenado con ceros a la izquierda)
    grosor_str = str(grosor).zfill(2)
    # 4 caracteres aleatorios
    while True:
        aleatorio = ''.join(random.choices(string.ascii_uppercase + string.digits, k=4))
        codigo = grosor_str + aleatorio
        # Verifica que no exista en la base de datos
        if not Bloque.query.filter_by(codigo_barra=codigo).first():
            return codigo

# Ruta principal para ver y crear órdenes
@ordenes_bp.route('/', methods=['GET', 'POST'])
def ordenes():
    error = None
    # Obtener todos los casos pendientes para mostrar en la interfaz de órdenes
    pendientes_orden = OrdenPendiente.query.order_by(OrdenPendiente.fecha_escaneo.asc()).all()
    # Si el usuario agrega un código pendiente desde la pestaña órdenes
    if request.method == 'POST' and 'codigo_orden_pendiente' in request.form:
        codigo_orden_pendiente = request.form.get('codigo_orden_pendiente', '').strip()
        if codigo_orden_pendiente and not OrdenPendiente.query.filter_by(codigo_orden=codigo_orden_pendiente).first():
            nuevo = OrdenPendiente(codigo_orden=codigo_orden_pendiente)
            db.session.add(nuevo)
            db.session.commit()
            flash('Código agregado a la lista de pendientes.')
        return redirect(url_for('ordenes.ordenes'))

    # Obtenemos los filtros de material y shade desde la URL
    material = request.args.get('material')
    shade = request.args.get('shade')

    # Obtener filtros de material y shade desde POST si existen (para mantener consistencia al crear orden)
    if request.method == 'POST':
        material_post = request.form.get('material')
        shade_post = request.form.get('shade')
        if material_post:
            material = material_post
        if shade_post:
            shade = shade_post

    # Obtener máquinas y materiales desde configuración
    maquinas = Configuracion.get_lista('maquinas')
    tipos_material = Configuracion.get_lista('materiales')

    # Obtenemos los tipos de material disponibles
    tipos_material = db.session.query(Bloque.material).distinct().all()
    tipos_material = [type[0] for type in tipos_material if type[0]]
    if not tipos_material:
        tipos_material = TIPOS_MATERIAL_FIJOS

    # --- FILTRO ROBUSTO DE SHADES ---
    # Normaliza el material para evitar problemas de espacios o mayúsculas
    material_normalizado = material.strip() if material else None
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
    if shade:
        bloques_usados_query = bloques_usados_query.filter(Bloque.shade == shade)
        bloques_nuevos_query = bloques_nuevos_query.filter(Bloque.shade == shade)
    bloques_usados = bloques_usados_query.all()
    bloques_nuevos = bloques_nuevos_query.all()

    # Si el formulario viene de la selección de casos pendientes (fresado grupal)
    codigos_seleccionados = request.form.getlist('codigos_seleccionados')
    # Solo procesar fresado grupal si también vienen los datos compartidos (material, shade, etc.)
    if codigos_seleccionados and request.method == 'POST' and 'material' in request.form:
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
        elif bloque_nuevo_id:
            bloque_nuevo = Bloque.query.get(int(bloque_nuevo_id))
            if bloque_nuevo and bloque_nuevo.cantidad > 0:
                bloque_nuevo.cantidad -= 1
                nuevo_bloque_usado = Bloque(
                    material=bloque_nuevo.material,
                    marca=bloque_nuevo.marca,
                    shade=bloque_nuevo.shade,
                    grosor=bloque_nuevo.grosor,
                    cantidad=1,
                    codigo_barra=generar_codigo_bloque(bloque_nuevo.grosor),
                    estado='usado',
                    modelos_fresados=cantidad_modelos * len(codigos_seleccionados),
                    codigos_orden_fresados=','.join(codigos_seleccionados),
                    fecha_creacion=datetime.utcnow()
                )
                db.session.add(nuevo_bloque_usado)
                bloque = nuevo_bloque_usado
                if bloque_nuevo.cantidad == 0:
                    db.session.delete(bloque_nuevo)
            else:
                error = "No hay bloques nuevos disponibles."
        if not bloque:
            if codigos_seleccionados:  # Solo mostrar error si hay pendientes seleccionados
                error = "Debes seleccionar un bloque usado o nuevo."
        else:
            # Creamos una orden para cada código seleccionado
            for codigo_orden in codigos_seleccionados:
                nueva_orden = Orden(
                    codigo_orden=codigo_orden,
                    material=bloque.material,
                    marca=bloque.marca,
                    shade=bloque.shade,
                    codigo_barra=bloque.codigo_barra,
                    maquina=maquina,
                    cantidad_modelos=cantidad_modelos,
                    fecha_creacion=datetime.utcnow()
                )
                db.session.add(nueva_orden)
                # Eliminamos el código de la lista de pendientes
                pendiente = OrdenPendiente.query.filter_by(codigo_orden=codigo_orden).first()
                if pendiente:
                    db.session.delete(pendiente)
            # Actualizamos la fresa instalada
            fresa_instalada = FresaInstalada.query.filter(
                FresaInstalada.maquina == maquina,
                FresaInstalada.materiales.like(f"%{bloque.material}%")
            ).order_by(FresaInstalada.fecha_instalacion.desc()).first()
            if fresa_instalada:
                fresa_instalada.modelos_fresados += cantidad_modelos * len(codigos_seleccionados)
            db.session.commit()
            flash('Órdenes grupales creadas correctamente.')
            return redirect(url_for('ordenes.ordenes', material=material_form, shade=shade_form))

    # Si el formulario es para crear una orden individual o múltiple (códigos separados por coma)
    if request.method == 'POST' and 'codigo_orden' in request.form:
        codigos_orden = request.form.get('codigo_orden', '').strip()
        if codigos_orden:
            codigos_lista = [c.strip() for c in codigos_orden.split(',') if c.strip()]
            modelos_por_caso_str = request.form.get('modelos_por_caso', '').strip()
            cantidad_modelos_total = int(request.form.get('cantidad_modelos', 1))
            # Procesar modelos por caso desde el input interactivo
            if modelos_por_caso_str:
                cantidades = []
                for x in modelos_por_caso_str.split(','):
                    try:
                        cantidades.append(int(x.strip()))
                    except ValueError:
                        cantidades.append(None)
                # Si hay valores vacíos o None, se completan con la división automática
                faltantes = [i for i, v in enumerate(cantidades) if not v]
                if faltantes:
                    # Calcular cuántos modelos quedan por repartir
                    suma_definidos = sum([v for v in cantidades if v])
                    restantes = max(cantidad_modelos_total - suma_definidos, 0)
                    base = restantes // len(faltantes) if faltantes else 0
                    resto = restantes % len(faltantes) if faltantes else 0
                    for idx, i in enumerate(faltantes):
                        cantidades[i] = base + (1 if idx < resto else 0)
                # Si la cantidad de cantidades no coincide con la de códigos, advertimos y usamos la división automática
                if len(cantidades) != len(codigos_lista):
                    error = 'La cantidad de modelos por caso no coincide con la cantidad de códigos. Se usará la división automática.'
                    base = cantidad_modelos_total // len(codigos_lista)
                    resto = cantidad_modelos_total % len(codigos_lista)
                    cantidades = [base + 1 if i < resto else base for i in range(len(codigos_lista))]
            else:
                # División automática si no se especifica nada
                base = cantidad_modelos_total // len(codigos_lista)
                resto = cantidad_modelos_total % len(codigos_lista)
                cantidades = [base + 1 if i < resto else base for i in range(len(codigos_lista))]
            material_form = request.form.get('material')
            shade_form = request.form.get('shade')
            maquina = request.form.get('maquina')
            bloque_usado_id = request.form.get('bloque_usado_id')
            bloque_nuevo_id = request.form.get('bloque_nuevo_id')
            bloque = None
            if bloque_usado_id:
                bloque = Bloque.query.get(int(bloque_usado_id))
                if bloque:
                    bloque.modelos_fresados += sum(cantidades)
                    codigos = bloque.get_codigos_orden_fresados()
                    codigos.extend(codigos_lista)
                    bloque.codigos_orden_fresados = ','.join(codigos)
            elif bloque_nuevo_id:
                bloque_nuevo = Bloque.query.get(int(bloque_nuevo_id))
                if bloque_nuevo and bloque_nuevo.cantidad > 0:
                    bloque_nuevo.cantidad -= 1
                    nuevo_bloque_usado = Bloque(
                        material=bloque_nuevo.material,
                        marca=bloque_nuevo.marca,
                        shade=bloque_nuevo.shade,
                        grosor=bloque_nuevo.grosor,
                        cantidad=1,
                        codigo_barra=generar_codigo_bloque(bloque_nuevo.grosor),
                        estado='usado',
                        modelos_fresados=sum(cantidades),
                        codigos_orden_fresados=','.join(codigos_lista),
                        fecha_creacion=datetime.utcnow()
                    )
                    db.session.add(nuevo_bloque_usado)
                    bloque = nuevo_bloque_usado
                    if bloque_nuevo.cantidad == 0:
                        db.session.delete(bloque_nuevo)
                else:
                    error = "No hay bloques nuevos disponibles."
            if not bloque:
                error = "Debes seleccionar un bloque usado o nuevo."
            else:
                for codigo_orden, cantidad_modelos in zip(codigos_lista, cantidades):
                    nueva_orden = Orden(
                        codigo_orden=codigo_orden,
                        material=bloque.material,
                        marca=bloque.marca,
                        shade=bloque.shade,
                        codigo_barra=bloque.codigo_barra,
                        maquina=maquina,
                        cantidad_modelos=cantidad_modelos,
                        fecha_creacion=datetime.utcnow()
                    )
                    db.session.add(nueva_orden)
                    pendiente = OrdenPendiente.query.filter_by(codigo_orden=codigo_orden).first()
                    if pendiente:
                        db.session.delete(pendiente)
                fresa_instalada = FresaInstalada.query.filter(
                    FresaInstalada.maquina == maquina,
                    FresaInstalada.materiales.like(f"%{bloque.material}%")
                ).order_by(FresaInstalada.fecha_instalacion.desc()).first()
                if fresa_instalada:
                    fresa_instalada.modelos_fresados += sum(cantidades)
                db.session.commit()
                flash('Órdenes creadas correctamente.')
                return redirect(url_for('ordenes.ordenes', material=material_form, shade=shade_form))

    # Obtenemos todas las órdenes para mostrarlas en la tabla
    ordenes = Orden.query.order_by(Orden.fecha_creacion.desc()).all()

    # Construir shades por material para el JS
    shades_por_material = {}
    for tipo in tipos_material:
        shades = db.session.query(Bloque.shade).filter(Bloque.material == tipo).distinct().all()
        shades_por_material[tipo] = [s[0] for s in shades if s[0]]

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
        error=error,
        pendientes_orden=pendientes_orden,
        shades_por_material=shades_por_material
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
    # Obtener listas desde configuración
    materiales = Configuracion.get_lista('materiales')
    marcas = Configuracion.get_lista('marcas')
    shades = Configuracion.get_lista('shades')
    maquinas = Configuracion.get_lista('maquinas')
    if request.method == 'POST':
        orden.codigo_orden = request.form['codigo_orden']
        orden.material = request.form['material']
        orden.marca = request.form['marca']
        orden.shade = request.form['shade']
        orden.maquina = request.form['maquina']
        orden.cantidad_modelos = request.form['cantidad_modelos']
        db.session.commit()
        flash('Orden actualizada correctamente.')
        return redirect(url_for('ordenes.ordenes'))
    return render_template('editar_orden.html', orden=orden, materiales=materiales, marcas=marcas, shades=shades, maquinas=maquinas)

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
    # Bloques por shade
    from models import Bloque, Orden
    # Bloques por shade (solo inventario actual)
    bloques_shade = (
        db.session.query(Bloque.shade, func.sum(Bloque.cantidad))
        .group_by(Bloque.shade)
        .all()
    )
    # Modelos fresados por máquina por semana (últimas 8 semanas)
    modelos_maquina = (
        db.session.query(
            func.to_char(Orden.fecha_creacion, 'IYYY-IW'),
            Orden.maquina,
            func.sum(Orden.cantidad_modelos)
        )
        .group_by(func.to_char(Orden.fecha_creacion, 'IYYY-IW'), Orden.maquina)
        .order_by(func.to_char(Orden.fecha_creacion, 'IYYY-IW').desc())
        .limit(32)
        .all()
    )
    # Modelos fresados por shade esta semana
    from datetime import datetime, timedelta
    hoy = datetime.utcnow()
    primer_dia_semana = hoy - timedelta(days=hoy.weekday())
    modelos_shade_semana = (
        db.session.query(Orden.shade, func.sum(Orden.cantidad_modelos))
        .filter(Orden.fecha_creacion >= primer_dia_semana)
        .group_by(Orden.shade)
        .all()
    )
    # Modelos fresados por material esta semana
    modelos_material_semana = (
        db.session.query(Orden.material, func.sum(Orden.cantidad_modelos))
        .filter(Orden.fecha_creacion >= primer_dia_semana)
        .group_by(Orden.material)
        .all()
    )
    # Modelos fresados por día (últimos 14 días)
    modelos_dia = (
        db.session.query(func.to_char(Orden.fecha_creacion, 'YYYY-MM-DD'), func.sum(Orden.cantidad_modelos))
        .group_by(func.to_char(Orden.fecha_creacion, 'YYYY-MM-DD'))
        .order_by(func.to_char(Orden.fecha_creacion, 'YYYY-MM-DD').desc())
        .limit(14)
        .all()
    )
    return jsonify({
        'bloques_shade': [{'shade': s, 'cantidad': int(c or 0)} for s, c in bloques_shade],
        'modelos_maquina': [{'semana': s, 'maquina': m, 'cantidad': int(c or 0)} for s, m, c in modelos_maquina],
        'modelos_shade_semana': [{'shade': s, 'cantidad': int(c or 0)} for s, c in modelos_shade_semana],
        'modelos_material_semana': [{'material': m, 'cantidad': int(c or 0)} for m, c in modelos_material_semana],
        'modelos_dia': [{'dia': d, 'cantidad': int(c or 0)} for d, c in modelos_dia],
    })