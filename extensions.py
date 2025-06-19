"""
Este archivo se encarga de inicializar la extensión de base de datos para Flask.

Paso a paso:
1. Se importa la clase SQLAlchemy, que permite trabajar con bases de datos de manera sencilla.
2. Se crea una instancia de SQLAlchemy llamada db, que se usará en toda la aplicación para definir y manipular la base de datos.

Este archivo permite que otros archivos importen y usen la base de datos fácilmente.
"""

# Importamos la clase SQLAlchemy de flask_sqlalchemy
from flask_sqlalchemy import SQLAlchemy

# Creamos la instancia de la base de datos que se usará en toda la app
# Esta variable 'db' se importa en otros archivos para definir modelos y manipular la base de datos

# Instancia global de la base de datos
# Se inicializa en app.py con la configuración de la app

# Creamos la instancia
db = SQLAlchemy()