"""
Este archivo contiene funciones auxiliares (utilidades) que ayudan a otras partes del sistema.

Paso a paso:
1. Se importan módulos para generar cadenas aleatorias.
2. Se importa el modelo Bloque para consultar la base de datos.
3. Se define una función para generar códigos de barra únicos para los bloques, combinando el grosor y un sufijo aleatorio.
4. La función revisa que el código generado no exista ya en la base de datos antes de devolverlo.

Estas utilidades facilitan tareas repetitivas o específicas que se usan en varias partes del proyecto.
"""

# Importamos módulos para generar cadenas aleatorias
import random
import string
from datetime import datetime
import pytz

VANCOUVER_TZ = pytz.timezone('America/Vancouver')
UTC_TZ = pytz.UTC

def current_utc():
    """Retorna la fecha/hora actual en UTC naive para almacenamiento consistente en BD."""
    return datetime.now(UTC_TZ).replace(tzinfo=None)

def to_vancouver_tz(dt):
    """Convierte cualquier fecha (naive UTC o aware) a fecha aware en America/Vancouver."""
    if not dt:
        return None
    if isinstance(dt, str):
        try:
            # Soporta formato ISO o estándar
            dt = datetime.fromisoformat(dt.replace('Z', '+00:00'))
        except Exception:
            try:
                dt = datetime.strptime(dt, '%Y-%m-%d %H:%M')
            except Exception:
                return None
    if dt.tzinfo is None:
        # Se asume que viene almacenado en UTC
        return UTC_TZ.localize(dt).astimezone(VANCOUVER_TZ)
    return dt.astimezone(VANCOUVER_TZ)

def vancouver_to_utc_naive(dt_or_str):
    """
    Toma una fecha o string proveniente de un input en hora local de Vancouver
    (como datetime-local 'YYYY-MM-DDTHH:MM') y la convierte a datetime naive en UTC.
    """
    if not dt_or_str:
        return None
    if isinstance(dt_or_str, str):
        dt_or_str = dt_or_str.strip()
        if not dt_or_str:
            return None
        parsed = None
        for fmt in ('%Y-%m-%dT%H:%M', '%Y-%m-%d %H:%M', '%Y-%m-%dT%H:%M:%S', '%Y-%m-%d'):
            try:
                parsed = datetime.strptime(dt_or_str, fmt)
                break
            except ValueError:
                continue
        if not parsed:
            return None
        dt_or_str = parsed

    if dt_or_str.tzinfo is None:
        # El usuario ingresó la hora en Vancouver
        localized = VANCOUVER_TZ.localize(dt_or_str)
    else:
        localized = dt_or_str.astimezone(VANCOUVER_TZ)
    return localized.astimezone(UTC_TZ).replace(tzinfo=None)

def format_vancouver(dt, fmt='%Y-%m-%d %H:%M'):
    """Formatea cualquier fecha a string en hora local de Vancouver."""
    if not dt:
        return ''
    van = to_vancouver_tz(dt)
    return van.strftime(fmt) if van else ''

def format_vancouver_input(dt):
    """Formatea cualquier fecha para el atributo value de un input datetime-local."""
    return format_vancouver(dt, fmt='%Y-%m-%dT%H:%M')

# Importamos el modelo Bloque para consultar la base de datos
from models import Bloque

# Función para generar un código de barra único para un bloque
# Recibe el grosor y genera un código que no exista en la base de datos
def generar_codigo_bloque(grosor):
    """
    Genera un código de barra único para un bloque, basado en el grosor y un sufijo aleatorio.
    """
    # Obtenemos todos los códigos de barra existentes en la base de datos
    existentes = {b.codigo_barra for b in Bloque.query.filter(Bloque.codigo_barra != None).all()}
    while True:
        # Generamos un sufijo aleatorio de 4 caracteres
        sufijo = ''.join(random.choices(string.ascii_uppercase + string.digits, k=4))
        # El código es el grosor (2 dígitos) más el sufijo
        codigo = f"{str(grosor).zfill(2)}{sufijo}"
        # Si el código no existe, lo devolvemos
        if codigo not in existentes:
            return codigo