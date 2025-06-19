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