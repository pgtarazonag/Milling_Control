"""
Este archivo es el punto de entrada de la aplicación web. Aquí se configura y se inicia la aplicación Flask, que es el servidor web que usaremos.

Paso a paso:
1. Se importa Flask y la función para renderizar plantillas HTML.
2. Se importa la base de datos (db) desde el archivo extensions.py.
3. Se define la función create_app(), que crea y configura la aplicación.
4. Se configuran los parámetros de la base de datos y la clave secreta.
5. Se inicializa la base de datos con la aplicación.
6. Se importan los modelos para que se creen las tablas en la base de datos.
7. Se importan y registran los blueprints (módulos) que organizan las diferentes partes de la app (órdenes, bloques, fresas, mantenimiento, historial).
8. Se define la ruta principal ('/') que muestra la página de inicio.
9. Se crea la base de datos si no existe.
10. Se retorna la aplicación lista para usarse.
11. Finalmente, si ejecutas este archivo directamente, se inicia el servidor en modo debug.
"""

# Importamos Flask y la función para renderizar plantillas HTML
from flask import Flask, render_template, session, request, redirect, url_for, jsonify, make_response, abort
# Importamos la base de datos desde extensions.py
from extensions import db, migrate
# Importamos la función de traducción
from translations import _
from flask_babel import Babel
import os
import pytz
from datetime import datetime
import json

if os.environ.get("RAILWAY_ENV") is None and os.environ.get("RENDER") is None:
    from dotenv import load_dotenv
    load_dotenv()

# Definimos la función principal que crea y configura la app
def create_app():
    # Creamos la instancia de la aplicación Flask
    app = Flask(__name__)
    # Configuramos la base de datos y la clave secreta
    db_url = os.environ.get('DATABASE_URL', 'sqlite:///fresado.db')
    # Normalizar esquema para SQLAlchemy
    if db_url.startswith('postgres://'):
        db_url = db_url.replace('postgres://', 'postgresql://', 1)
    # Asegurar SSL en plataformas hospedadas si no está presente
    if db_url.startswith('postgresql://') and 'sslmode=' not in db_url and (
        os.environ.get('RAILWAY_ENV') or os.environ.get('RENDER') or os.environ.get('FLY_APP_NAME')
    ):
        db_url = f"{db_url}{'&' if '?' in db_url else '?'}sslmode=require"
    app.config['SQLALCHEMY_DATABASE_URI'] = db_url
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
    app.secret_key = os.environ.get('SECRET_KEY', 'supersecreto')
    # Configuración de Babel para traducción
    app.config['BABEL_DEFAULT_LOCALE'] = 'en'
    app.config['BABEL_SUPPORTED_LOCALES'] = ['en', 'es']
    babel = Babel(app)

    # Versión de assets para cache busting (usa SHA de deploy si existe)
    # Use timezone-aware UTC timestamp to avoid DeprecationWarning on Python 3.13+
    app.config['ASSET_VERSION'] = (
        os.environ.get('ASSET_VERSION') or
        os.environ.get('RAILWAY_GIT_COMMIT_SHA') or
        os.environ.get('RENDER_GIT_COMMIT') or
        datetime.now(pytz.UTC).strftime('%Y%m%d%H%M%S')
    )

    # Inicializamos la base de datos con la app
    db.init_app(app)
    migrate.init_app(app, db)

    @app.template_filter('vancouver')
    def vancouver_filter(dt):
        if not dt:
            return ''
        tz = pytz.timezone('America/Vancouver')
        if dt.tzinfo:
            return dt.astimezone(tz).strftime('%Y-%m-%d %H:%M')
        else:
            # Si viene naive, asumir UTC
            return dt.replace(tzinfo=pytz.UTC).astimezone(tz).strftime('%Y-%m-%d %H:%M')

    # Importamos los modelos para que se creen las tablas
    import models

    # Importamos y registramos los blueprints (módulos de rutas)
    from routes.ordenes import ordenes_bp
    from routes.bloques import bloques_bp
    from routes.fresas import fresas_bp
    from routes.mantenimiento import mantenimiento_bp
    from routes.historial_bloques import historial_bp
    from routes.configuracion import configuracion_bp

    app.register_blueprint(ordenes_bp)  # Rutas de órdenes
    app.register_blueprint(bloques_bp)  # Rutas de bloques
    app.register_blueprint(fresas_bp)   # Rutas de fresas
    app.register_blueprint(mantenimiento_bp)  # Rutas de mantenimiento
    app.register_blueprint(historial_bp)      # Rutas de historial
    app.register_blueprint(configuracion_bp)  # Rutas de configuración

    # Ruta para cambiar el idioma
    @app.route('/set_language', methods=['POST'])
    def set_language():
        lang = request.form.get('lang', 'en')
        session['lang'] = 'en' if lang not in ('en', 'es') else lang
        return redirect(request.referrer or url_for('home'))

    # Establecer inglés como idioma por defecto en la sesión
    @app.before_request
    def ensure_default_language():
        if 'lang' not in session:
            session['lang'] = 'en'

    # Inyectar el traductor y versión de assets en las plantillas
    @app.context_processor
    def inject_globals():
        return {'_': _, 'ASSET_VERSION': app.config.get('ASSET_VERSION', '')}

    # Atajo para /favicon.ico (algunos navegadores la piden aunque esté linkeada)
    @app.route('/favicon.ico')
    def favicon():
        v = app.config.get('ASSET_VERSION', '')
        return redirect(url_for('static', filename='favicon-32.png', v=v))

    # Definimos la ruta principal que muestra la página de inicio
    @app.route('/')
    def home():
        # Obtener materiales, marcas y configuración avanzada para los filtros
        from models import Bloque, FresaInventario, Configuracion, Orden
        tipos_material = db.session.query(Bloque.material).distinct().all()
        tipos_material = [m[0] for m in tipos_material if m[0]]
        marcas = db.session.query(Bloque.marca).distinct().all()
        marcas = [m[0] for m in marcas if m[0]]
        # Obtener configuración avanzada de materiales
        try:
            materiales_avanzado = Configuracion.get_lista('materiales_avanzado')
            if isinstance(materiales_avanzado, dict):
                pass
            elif materiales_avanzado and isinstance(materiales_avanzado, list) and isinstance(materiales_avanzado[0], str) and materiales_avanzado[0].startswith('{'):
                import json
                materiales_avanzado = json.loads(materiales_avanzado[0])
            else:
                materiales_avanzado = {}
        except Exception:
            materiales_avanzado = {}
        # Obtener configuración de máquinas para el filtro en la gráfica de fresas nuevas
        try:
            fresas_maquinas = Configuracion.get_lista('fresas_maquinas')
            if isinstance(fresas_maquinas, dict):
                pass
            elif fresas_maquinas and isinstance(fresas_maquinas, list) and isinstance(fresas_maquinas[0], str) and fresas_maquinas[0].startswith('{'):
                import json
                fresas_maquinas = json.loads(fresas_maquinas[0])
            else:
                fresas_maquinas = {}
        except Exception:
            fresas_maquinas = {}
        maquinas = Configuracion.get_lista('maquinas', default=['A','B','C','D'])
        fresas_nuevas = db.session.query(FresaInventario).all()
        # Calcular resumen del día (zona horaria Vancouver)
        tz = pytz.timezone('America/Vancouver')
        hoy = datetime.now(tz).date()
        from sqlalchemy import or_
        def to_vancouver(dt):
            if dt is None:
                return None
            if dt.tzinfo:
                return dt.astimezone(tz)
            else:
                return dt.replace(tzinfo=pytz.UTC).astimezone(tz)
        ordenes_hoy = []
        for o in db.session.query(Orden).all():
            dt = to_vancouver(o.fecha_creacion)
            if dt and dt.date() == hoy:
                ordenes_hoy.append(o)
        total_ordenes = len(ordenes_hoy)
        total_casos = sum(len(o.get_codigos_caso()) for o in ordenes_hoy)
        total_modelos = sum(o.cantidad_modelos or 0 for o in ordenes_hoy)
        return render_template(
            'home.html',
            tipos_material=tipos_material,
            marcas=marcas or [],
            fresas_nuevas=fresas_nuevas,
            materiales_avanzado=materiales_avanzado or {},
            maquinas=maquinas,
            fresas_maquinas=fresas_maquinas or {},
            total_ordenes=total_ordenes,
            total_casos=total_casos,
            total_modelos=total_modelos
        )

    # Ruta para obtener la hora actual de Vancouver
    @app.route('/api/hora-vancouver')
    def api_hora_vancouver():
        tz = pytz.timezone('America/Vancouver')
        ahora = datetime.now(tz)
        return jsonify({
            'fecha_hora': ahora.strftime('%Y-%m-%d %H:%M'),
            'iso': ahora.isoformat(),
            'zona': 'America/Vancouver'
        })

    # Seguridad: permitir sin token solo en entorno local/desarrollo
    def is_dev_or_local():
        if app.debug:
            return True
        # Consideramos "local" si no estamos en plataformas hospedadas y la petición viene de localhost
        if not os.environ.get('RENDER') and not os.environ.get('RAILWAY_ENV'):
            ip = (request.remote_addr or '')
            host = (request.host or '')
            return ip in ('127.0.0.1', '::1') or host.startswith('localhost') or host.startswith('127.0.0.1')
        return False

    def enforce_backup_auth():
        expected = os.environ.get('BACKUP_TOKEN')
        token = request.args.get('token') or request.headers.get('X-Backup-Token')
        if expected:
            if token != expected:
                abort(403)
        else:
            # Si no hay token configurado, solo permitir en local/desarrollo
            if not is_dev_or_local():
                abort(403)

    # Ruta: Backup completo de la base de datos (JSON)
    @app.route('/backup', methods=['GET'])
    def backup_db():
        enforce_backup_auth()
        # Importar modelos localmente para evitar dependencias circulares
        from models import (
            Orden, Bloque, BloqueHistorial, FresaInventario,
            FresaInstalada, Mantenimiento, OrdenPendiente, Configuracion
        )
        modelos = [
            Orden, Bloque, BloqueHistorial, FresaInventario,
            FresaInstalada, Mantenimiento, OrdenPendiente, Configuracion
        ]
        def serialize_row(obj):
            data = {}
            for col in obj.__table__.columns:
                val = getattr(obj, col.name)
                if isinstance(val, datetime):
                    try:
                        data[col.name] = val.isoformat()
                    except Exception:
                        data[col.name] = val.strftime('%Y-%m-%dT%H:%M:%S')
                else:
                    data[col.name] = val
            return data
        payload = {}
        for m in modelos:
            rows = m.query.all()
            payload[m.__name__] = [serialize_row(r) for r in rows]
        content = json.dumps(payload, ensure_ascii=False, indent=2)
        resp = make_response(content)
        resp.headers['Content-Type'] = 'application/json; charset=utf-8'
        ts = datetime.now().strftime('%Y%m%d_%H%M%S')
        resp.headers['Content-Disposition'] = f'attachment; filename=fresado_backup_{ts}.json'
        return resp

    # Ruta: Restaurar backup (JSON). Modo por defecto: merge. Para limpiar antes: /restore?mode=wipe
    @app.route('/restore', methods=['POST'])
    def restore_db():
        enforce_backup_auth()
        if 'file' not in request.files:
            return jsonify({'status': 'error', 'msg': 'Falta archivo'}), 400
        file = request.files['file']
        try:
            payload = json.load(file)
        except Exception as e:
            return jsonify({'status': 'error', 'msg': f'JSON inválido: {e}'}), 400
        mode = (request.args.get('mode') or 'merge').lower()
        from models import (
            Orden, Bloque, BloqueHistorial, FresaInventario,
            FresaInstalada, Mantenimiento, OrdenPendiente, Configuracion
        )
        modelos = {
            'Orden': Orden,
            'Bloque': Bloque,
            'BloqueHistorial': BloqueHistorial,
            'FresaInventario': FresaInventario,
            'FresaInstalada': FresaInstalada,
            'Mantenimiento': Mantenimiento,
            'OrdenPendiente': OrdenPendiente,
            'Configuracion': Configuracion,
        }
        # Utilidad: detectar columnas datetime
        def datetime_cols(model):
            return {c.name for c in model.__table__.columns if getattr(c.type, '__class__', type('t', (), {})).__name__ == 'DateTime'}
        def parse_dt(val):
            if not isinstance(val, str):
                return val
            try:
                # Soporta 'YYYY-MM-DDTHH:MM:SS[.fff][+/-TZ]'
                return datetime.fromisoformat(val.replace('Z', '+00:00'))
            except Exception:
                return val
        # Limpieza si corresponde
        if mode == 'wipe':
            # Borrar en un orden seguro; no hay FKs explícitas, pero empezamos por dependientes posibles
            for name in ['OrdenPendiente', 'Mantenimiento', 'FresaInstalada', 'FresaInventario', 'BloqueHistorial', 'Orden', 'Bloque', 'Configuracion']:
                modelos[name].query.delete()
            db.session.commit()
        total_insert = 0
        total_update = 0
        for name, rows in payload.items():
            Model = modelos.get(name)
            if not Model:
                continue
            dt_fields = datetime_cols(Model)
            for raw in rows or []:
                data = dict(raw)
                for k in list(data.keys()):
                    if k in dt_fields and data[k] is not None:
                        data[k] = parse_dt(data[k])
                obj = None
                # upsert por id si existe
                if 'id' in data and data['id'] is not None:
                    obj = Model.query.get(data['id'])
                if obj is None:
                    obj = Model(**data)
                    db.session.add(obj)
                    total_insert += 1
                else:
                    for k, v in data.items():
                        setattr(obj, k, v)
                    total_update += 1
        db.session.commit()
        return jsonify({'status': 'ok', 'mode': mode, 'inserted': total_insert, 'updated': total_update})

    # Creamos las tablas de la base de datos si no existen.
    # Nota: en entornos hospedados la base de datos puede no estar lista
    # inmediatamente al arrancar; evitamos que la aplicación falle en ese caso
    # registrando una advertencia en lugar de propagar la excepción.
    from sqlalchemy.exc import OperationalError
    with app.app_context():
        try:
            db.create_all()
        except OperationalError as e:
            # Registrar advertencia y seguir; la infra debería intentar
            # reconectar más tarde o ejecutar migraciones por separado.
            try:
                app.logger.warning('Database not available at startup: %s', e)
            except Exception:
                # Si logger no está listo, imprimir como fallback
                print('Warning: Database not available at startup:', e)

    # NOTA: Cuando el usuario selecciona varios códigos de la lista de pendientes y presiona "Fresar seleccionados",
    # se debe redirigir a un formulario donde se completan los datos compartidos (shade, material, bloque, etc.)
    # para todos los códigos seleccionados. Luego, se crean las órdenes y se eliminan de la lista de pendientes.
    # Esta integración se debe realizar en la lógica de la ruta de órdenes.

    # Retornamos la app lista para usarse
    return app

# Expose a WSGI application object for Gunicorn and other WSGI servers.
# This makes the process invocation simpler (e.g. `gunicorn app:application`).
# We keep the development `if __name__ == '__main__'` block below unchanged.
try:
    # Delay creation until module import; if environment isn't configured
    # this will raise later when the process starts — that's expected.
    application = create_app()
except Exception:
    # If creation at import time fails (e.g., missing DB in build phase),
    # do not crash here; Gunicorn or the runtime will show real error on start.
    application = None

# Si este archivo se ejecuta directamente, inicia el servidor en modo debug
if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app = create_app()
    app.run(debug=True, host='0.0.0.0', port=port)