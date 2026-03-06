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
    # Códigos de caso asociados a la orden (separados por coma)
    codigos_caso = db.Column(db.Text)
    # Material usado en la orden
    material = db.Column(db.String(50))
    # Marca del material
    marca = db.Column(db.String(50))
    # Color o shade del material
    shade = db.Column(db.String(255))
    # Código de barra del bloque usado (JSON list for Titanium, Single String for Zirconia)
    codigo_barra = db.Column(db.Text) 
    # Máquina utilizada
    maquina = db.Column(db.String(50))
    # Cantidad de modelos fresados en la orden
    cantidad_modelos = db.Column(db.Integer)
    # Fecha de creación de la orden
    fecha_creacion = db.Column(db.DateTime, default=datetime.utcnow)
    # Holder para aditamentos de titanio
    aditamento_holder = db.Column(db.String(50))

    def get_codigos_caso(self):
        # Devuelve una lista de los códigos de caso asociados a la orden
        if self.codigos_caso:
            return [c.strip() for c in self.codigos_caso.split(',') if c.strip()]
        return []

    def get_lista_codigos_barras(self):
        # Parses codigo_barra as a list if strictly needed, assumes comma separated or JSON
        if not self.codigo_barra:
            return []
        if self.codigo_barra.startswith('[') and self.codigo_barra.endswith(']'):
            import json
            try:
                return json.loads(self.codigo_barra)
            except:
                return [self.codigo_barra]
        return [self.codigo_barra]

# Modelo para los bloques de material
class Bloque(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    material = db.Column(db.String(50), nullable=False)
    marca = db.Column(db.String(50))
    shade = db.Column(db.String(255))
    grosor = db.Column(db.Integer)
    cantidad = db.Column(db.Integer, default=1)
    codigo_barra = db.Column(db.String(100))
    estado = db.Column(db.String(20), default='nuevo')
    codigo_referencia = db.Column(db.String(100)) # Manufacturer SKU
    modelos_fresados = db.Column(db.Integer, default=0)
    codigos_orden_fresados = db.Column(db.Text)
    fecha_creacion = db.Column(db.DateTime, default=datetime.utcnow)
    # Holder/System for titanium blocks
    aditamento_holder = db.Column(db.String(50))

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
    shade = db.Column(db.String(255))
    grosor = db.Column(db.Integer)
    cantidad = db.Column(db.Integer)
    codigo_barra = db.Column(db.String(100))
    codigo_referencia = db.Column(db.String(100)) # Manufacturer SKU
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
    proxima_fecha = db.Column(db.DateTime)

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
            valor = c.valor.strip()
            if (valor.startswith('{') and valor.endswith('}')) or (valor.startswith('[') and valor.endswith(']')):
                import json
                try:
                    return json.loads(valor)
                except Exception:
                    # Si falla el JSON, intentar como lista separada por comas
                    return [x.strip() for x in valor.split(',') if x.strip()]
            return [x.strip() for x in valor.split(',') if x.strip()]
        return default or []
    
    @staticmethod
    def get_valor(clave, default=None):
        """Get a simple string value from configuration"""
        c = Configuracion.query.filter_by(clave=clave).first()
        if c:
            return c.valor
        return default or ''
    
    @staticmethod
    def set_valor(clave, valor):
        """Set a simple string value in configuration"""
        c = Configuracion.query.filter_by(clave=clave).first()
        if not c:
            c = Configuracion(clave=clave, valor=str(valor))
            db.session.add(c)
        else:
            c.valor = str(valor)
        db.session.commit()
    
    @staticmethod
    def set_lista(clave, lista):
        """Set a list value in configuration"""
        c = Configuracion.query.filter_by(clave=clave).first()
        # Si es una lista con un solo elemento que parece JSON, guardar tal cual
        if isinstance(lista, list) and len(lista) == 1 and (str(lista[0]).strip().startswith('{') or str(lista[0]).strip().startswith('[')):
            valor = str(lista[0]).strip()
        else:
            valor = ','.join(lista)
        if not c:
            c = Configuracion(clave=clave, valor=valor)
            db.session.add(c)
        else:
            c.valor = valor
        db.session.commit()

# Modelo para Auditoría de Bloques (Log changes)
class LogInventario(db.Model):
    __tablename__ = 'log_inventario'
    id = db.Column(db.Integer, primary_key=True)
    fecha = db.Column(db.DateTime, default=datetime.utcnow)
    accion = db.Column(db.String(50))  # CREACION, ELIMINACION, EDICION, CONVERSION, STOCK_UPDATE
    bloque_id = db.Column(db.Integer, nullable=True) # Referencia al bloque relacionado
    descripcion = db.Column(db.String(500)) # Detalle legible
    detalles = db.Column(db.Text) # JSON string opcional para valores old/new
    usuario = db.Column(db.String(50), default='System')