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
from flask import Flask, render_template, session, request, redirect, url_for, jsonify
# Importamos la base de datos desde extensions.py
from extensions import db
# Importamos la función de traducción
from translations import _
from flask_babel import Babel
import os
import pytz
from datetime import datetime

if os.environ.get("RAILWAY_ENV") is None and os.environ.get("RENDER") is None:
    from dotenv import load_dotenv
    load_dotenv()

# Definimos la función principal que crea y configura la app
def create_app():
    # Creamos la instancia de la aplicación Flask
    app = Flask(__name__)
    # Configuramos la base de datos y la clave secreta
    app.config['SQLALCHEMY_DATABASE_URI'] = os.environ.get('DATABASE_URL', 'sqlite:///fresado.db')
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
    app.secret_key = os.environ.get('SECRET_KEY', 'supersecreto')
    # Configuración de Babel para traducción
    app.config['BABEL_DEFAULT_LOCALE'] = 'es'
    app.config['BABEL_SUPPORTED_LOCALES'] = ['es', 'en']
    babel = Babel(app)
    # Inicializamos la base de datos con la app
    db.init_app(app)

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
        lang = request.form.get('lang', 'es')
        session['lang'] = lang
        return redirect(request.referrer or url_for('home'))

    # Inyectar el traductor en las plantillas
    @app.context_processor
    def inject_translator():
        return {'_': _}

    # Definimos la ruta principal que muestra la página de inicio
    @app.route('/')
    def home():
        # Obtener materiales, marcas y configuración avanzada para los filtros
        from models import Bloque, FresaInventario, Configuracion
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
        return render_template('home.html', tipos_material=tipos_material, marcas=marcas, fresas_nuevas=fresas_nuevas, materiales_avanzado=materiales_avanzado, maquinas=maquinas, fresas_maquinas=fresas_maquinas)

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

    # Creamos las tablas de la base de datos si no existen
    with app.app_context():
        db.create_all()

    # NOTA: Cuando el usuario selecciona varios códigos de la lista de pendientes y presiona "Fresar seleccionados",
    # se debe redirigir a un formulario donde se completan los datos compartidos (shade, material, bloque, etc.)
    # para todos los códigos seleccionados. Luego, se crean las órdenes y se eliminan de la lista de pendientes.
    # Esta integración se debe realizar en la lógica de la ruta de órdenes.

    # Retornamos la app lista para usarse
    return app

# Si este archivo se ejecuta directamente, inicia el servidor en modo debug
if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app = create_app()
    app.run(debug=True, host='0.0.0.0', port=port)