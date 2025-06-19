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
from flask import Flask, render_template, session, request, redirect, url_for
# Importamos la base de datos desde extensions.py
from extensions import db
# Importamos la función de traducción
from translations import _

# Definimos la función principal que crea y configura la app
def create_app():
    # Creamos la instancia de la aplicación Flask
    app = Flask(__name__)
    # Configuramos la base de datos y la clave secreta
    app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///fresado.db'
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
    app.secret_key = 'supersecreto'
    # Inicializamos la base de datos con la app
    db.init_app(app)

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
        return render_template('home.html')

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
    app = create_app()
    app.run(debug=True)