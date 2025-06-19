"""
Este archivo define los modelos de datos, es decir, las estructuras que representan las tablas de la base de datos.

Paso a paso:
1. Se importa la base de datos (db) y la fecha/hora actual.
2. Se definen varias clases, cada una representa una tabla:
   - Orden: almacena información de cada orden de fresado.
   - Bloque: representa los bloques de material disponibles o usados.
   - BloqueHistorial: guarda el historial de bloques eliminados o modificados.
   - FresaInventario: inventario de fresas nuevas.
   - FresaInstalada: fresas que están instaladas en las máquinas.
   - Mantenimiento: registro de actividades de mantenimiento.
3. Cada clase tiene atributos que corresponden a las columnas de la tabla.
4. Algunas clases tienen métodos para procesar datos almacenados (por ejemplo, obtener los códigos de orden fresados).

En resumen, aquí se define cómo se almacena y organiza la información principal del sistema.
"""

# Importamos la base de datos y la fecha/hora actual
from extensions import db
from datetime import datetime

# Modelo para las órdenes de fresado
class Orden(db.Model):
    # id único para cada orden
    id = db.Column(db.Integer, primary_key=True)
    # Código de la orden
    codigo_orden = db.Column(db.String(100))
    # Material usado en la orden
    material = db.Column(db.String(50))
    # Marca del material
    marca = db.Column(db.String(50))
    # Color o shade del material
    shade = db.Column(db.String(20))
    # Código de barra del bloque usado
    codigo_barra = db.Column(db.String(100))
    # Máquina utilizada
    maquina = db.Column(db.String(50))
    # Cantidad de modelos fresados en la orden
    cantidad_modelos = db.Column(db.Integer)
    # Fecha de creación de la orden
    fecha_creacion = db.Column(db.DateTime, default=datetime.utcnow)

# Modelo para los bloques de material
class Bloque(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    material = db.Column(db.String(50), nullable=False)
    marca = db.Column(db.String(50))
    shade = db.Column(db.String(20))
    grosor = db.Column(db.Integer)
    cantidad = db.Column(db.Integer, default=1)
    codigo_barra = db.Column(db.String(100))
    estado = db.Column(db.String(20), default='nuevo')
    modelos_fresados = db.Column(db.Integer, default=0)
    codigos_orden_fresados = db.Column(db.Text)
    fecha_creacion = db.Column(db.DateTime, default=datetime.utcnow)

    def get_codigos_orden_fresados(self):
        # Devuelve una lista de los códigos de orden fresados en este bloque
        if self.codigos_orden_fresados:
            return [c for c in self.codigos_orden_fresados.split(',') if c]
        return []

# Modelo para el historial de bloques eliminados o modificados
class BloqueHistorial(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    bloque_id = db.Column(db.Integer)
    material = db.Column(db.String(50))
    marca = db.Column(db.String(50))
    shade = db.Column(db.String(20))
    grosor = db.Column(db.Integer)
    cantidad = db.Column(db.Integer)
    codigo_barra = db.Column(db.String(100))
    estado = db.Column(db.String(20))
    modelos_fresados = db.Column(db.Integer)
    codigos_orden_fresados = db.Column(db.Text)
    fecha_creacion = db.Column(db.DateTime)
    fecha_eliminacion = db.Column(db.DateTime, default=datetime.utcnow)

    def get_codigos_orden_fresados(self):
        # Devuelve una lista de los códigos de orden fresados en este bloque (historial)
        if self.codigos_orden_fresados:
            return [c for c in self.codigos_orden_fresados.split(',') if c]
        return []

# Modelo para el inventario de fresas nuevas
class FresaInventario(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    tipo = db.Column(db.String(50))
    diametro = db.Column(db.Float)
    cantidad = db.Column(db.Integer, default=1)
    materiales = db.Column(db.String(200))  # Materiales compatibles, separados por coma
    fecha_registro = db.Column(db.DateTime, default=datetime.utcnow)

# Modelo para las fresas instaladas en las máquinas
class FresaInstalada(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    tipo = db.Column(db.String(50))
    diametro = db.Column(db.Float)
    maquina = db.Column(db.String(50))
    materiales = db.Column(db.String(200))  # Materiales compatibles, separados por coma
    fecha_instalacion = db.Column(db.DateTime, default=datetime.utcnow)
    modelos_fresados = db.Column(db.Integer, default=0)

# Modelo para el registro de mantenimiento de las máquinas
class Mantenimiento(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    maquina = db.Column(db.String(100))
    actividad = db.Column(db.String(200))
    descripcion = db.Column(db.String(200))
    fecha = db.Column(db.DateTime, default=datetime.utcnow)

"""
Modelo para almacenar los códigos de orden que han sido escaneados y están pendientes de ser fresados.
Cada vez que se escanea un código (el escáner envía un ENTER), se agrega una nueva entrada aquí.
Luego, el usuario puede seleccionar uno o varios códigos de esta lista para crear una orden grupal.
Todas las órdenes agrupadas compartirán los mismos datos de shade, material, bloque, etc.
"""
class OrdenPendiente(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    codigo_orden = db.Column(db.String(100), unique=True)
    fecha_escaneo = db.Column(db.DateTime, default=datetime.utcnow)
    # Puedes agregar más campos si lo necesitas en el futuro

# Modelo para almacenar configuraciones y listas editables
class Configuracion(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    clave = db.Column(db.String(50), unique=True, nullable=False)
    valor = db.Column(db.Text, nullable=False)

    @staticmethod
    def get_lista(clave, default=None):
        c = Configuracion.query.filter_by(clave=clave).first()
        if c:
            return [x.strip() for x in c.valor.split(',') if x.strip()]
        return default or []

    @staticmethod
    def set_lista(clave, lista):
        c = Configuracion.query.filter_by(clave=clave).first()
        if not c:
            c = Configuracion(clave=clave, valor=','.join(lista))
            db.session.add(c)
        else:
            c.valor = ','.join(lista)
        db.session.commit()