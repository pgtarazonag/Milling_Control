# Milling_Control — README (Desarrollo)

Este documento explica cómo poner en marcha el proyecto en un entorno de desarrollo, cómo desplegar en Railway y contiene notas operativas y de troubleshooting para que el nuevo desarrollador o agente Copilot entienda rápidamente el estado del proyecto.

---
## Resumen rápido
- Aplicación: Flask + SQLAlchemy para gestionar un laboratorio dental (órdenes, bloques, fresas, mantenimiento, historial).
- Lenguaje: Python 3.12/3.13 (Nixpacks en producción usa python312).
- Frontend: Jinja2 + Bootstrap 5 + DataTables + Chart.js.
- Start recomendado en producción: `gunicorn -w 2 -k gthread -b 0.0.0.0:$PORT app:application`.
- Nota: `app.py` expone `application = create_app()` para servidores WSGI.

---
## Requisitos locales
- Python 3.11+ (3.12/3.13 preferible para paridad con prod).
- pip
- git
- (Opcional en Windows) WSL2 si prefieres usar Gunicorn nativo Linux.

---
## Configuración rápida (Windows PowerShell)
1. Clona el repo y entra al directorio:

```powershell
git clone https://github.com/pgtarazonag/Milling_Control.git
cd Milling_Control
```

2. Crea y activa un entorno virtual (PowerShell):

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install --upgrade pip
pip install -r requirements.txt
```

3. Variables de entorno (modo desarrollo): crea un archivo `.env` o exporta en PowerShell:

```powershell
# Ejemplo .env (si usas python-dotenv, que ya está en el proyecto)
# DATABASE_URL puede ser sqlite para desarrollo
DATABASE_URL="sqlite:///fresado.db"
SECRET_KEY="dev-secret"
BACKUP_TOKEN="local-token"
ASSET_VERSION=dev
```

4. Ejecutar la app en modo desarrollo:

```powershell
# Usando flask (rápido para dev)
set FLASK_APP=app.py
flask run
# O (en Windows) usar waitress si prefieres WSGI:
pip install waitress
waitress-serve --listen=*:5000 app:application
```

5. Para replicar producción (recomendado en WSL o Linux):

```bash
pip install gunicorn
gunicorn -w 2 -k gthread -b 0.0.0.0:5000 app:application
```

> Nota: Gunicorn no es nativamente compatible con Windows; si trabajas en Windows usa `waitress` o WSL.

---
## Endpoints útiles para desarrollo
- `/` — Home (dashboard)
- `/ordenes` — Gestión de órdenes
- `/bloques` — Gestión de bloques (inventario)
- `/fresas` — Fresas instaladas/inventario
- `/mantenimiento` — Mantenimientos y próximas actividades
- `/historial` — Historial y exportación Excel
- `/backup` — Descarga JSON de backup (protegido por `BACKUP_TOKEN` o accesible en local)
- `/restore` — Restaurar backup (POST multipart/form-data)

---
## Notas sobre la base de datos
- En desarrollo se puede usar SQLite `sqlite:///fresado.db`.
- En producción usamos PostgreSQL (Railway). `app.py` normaliza `postgres://` → `postgresql://` y añade `sslmode=require` si detecta `RAILWAY_ENV` o `RENDER`.

### Migraciones
- Actualmente el proyecto usa `db.create_all()` (instanciado en `create_app()`), aunque se ha envuelto para evitar crash si la DB no está lista.
- Recomendación: añadir Flask-Migrate / Alembic y reemplazar `create_all()` por `flask db upgrade` en el pipeline.

---
## Variables de entorno que debes configurar (mínimo)
- `DATABASE_URL` — Cadena de conexión a Postgres o sqlite.
- `SECRET_KEY` — Clave secreta Flask.
- `BACKUP_TOKEN` — Token para `/backup` y `/restore`.
- `ASSET_VERSION` — (opcional) para cache-busting.
- `PORT` — puerto que gestiona el proceso en prod (Railway setea esto).
- `RAILWAY_ENV` / `RENDER` — flags que `app.py` usa para comportamientos específicos (opcional).

---
## Start command recomendado (Railway / Nixpacks / Procfile)
- Railway: en la configuración del servicio, establece el start command a:

```
gunicorn -w 2 -k gthread -b 0.0.0.0:$PORT app:application
```

- Si usas `Procfile`, añade:

```
web: gunicorn -w 2 -k gthread -b 0.0.0.0:$PORT app:application
```

> Evita usar `app:create_app()` con paréntesis en la configuración de start: muchas plataformas tienen problemas al parsear paréntesis.

---
## Troubleshooting (errores comunes)

### 1) Error al iniciar: `failed to parse start command 'gunicorn ... app:create_app()'`
- Causa: el sistema no parsea paréntesis. Solución: usar `app:application` y asegurar que `application` esté exportado (ya está en `app.py`).

### 2) Traceback `the database system is starting up` o `OperationalError` al arrancar
- Causa: el contenedor de Postgres aún está inicializándose cuando la app intenta conectar y `db.create_all()` se ejecuta.
- Estado actual: `app.py` captura `OperationalError` para que la app no muera al arrancar y registra una advertencia.
- Recomendación: preferir migraciones y/o implementar un pequeño retry/backoff antes de dar por fallida la creación de tablas.

### 3) `DeprecationWarning` por `datetime.utcnow()` (Python 3.13+)
- Solución ya aplicada: `ASSET_VERSION` usa `datetime.now(pytz.UTC)` para evitar la advertencia.

### 4) Gunicorn en Windows
- Gunicorn no funciona bien en Windows. Usa WSL o `waitress` para entorno local en Windows.

---
## Notas de desarrollo y arquitectura
- i18n: `translations.py` con helper `_()`; Babel configura locales `en` y `es`.
- UI: la terminología estándar es ahora `# Units` en lugar de `Models`.
- Assets: `ASSET_VERSION` inyectado en plantillas para cache-busting.
- Backups: `/backup` y `/restore` permiten export/import JSON, protegidos por `BACKUP_TOKEN`.

---
## Recomendaciones para el próximo desarrollador
1. Revisar `models.py` para entender el esquema y añadir migraciones con Flask-Migrate.
2. Revisar `routes/` para ver la lógica de cada módulo y tests que cubrirían API JSON y utilidades.
3. Reforzar la inicialización de DB: introducir retry/backoff o separar `create_all()` a un script `scripts/init_db.py`.
4. Añadir `README_DEV.md` (este archivo) al repo y referenciarlo desde `README.md` principal.

---
## Cómo contribuir y flujos de trabajo sugeridos
- Branches: crear ramas por feature/bug (ej. `feature/maintenance-ui`), push a remoto y abrir PR contra `main`.
- Commits: mensaje tipo Conventional Commits (ej. `fix(deploy): ...`, `feat(ui): ...`).

---
## Recursos y logs
- Logs de Railway: revisa logs de despliegue/arranque y `docker logs` si corres localmente en contenedor.
- En caso de error reproducible, copia el stacktrace y revisa la línea en `app.py`/`models.py`/`routes/*` implicada.

---
## Contacto y contexto
- Contexto del proyecto: software para un laboratorio dental en Vancouver; 4 CNCs; manejo de bloques por shade y grosor; sinterizado en hornos; control de inventario y mantenimiento.
- Para dudas de diseño preguntar al responsable del repo (propietario GitHub `pgtarazonag`) o revisar los commit messages recientes para entender el historial de cambios.

---
## Últimos pasos recomendados (si empiezas en otra máquina)
1. Clona, crea venv e instala deps.
2. Copia `.env` con `DATABASE_URL` apuntando a sqlite para pruebas locales.
3. Arranca con `flask run` o `waitress` y accede a `/`.
4. Revisa y prueba backup/restore con un pequeño JSON.
5. Lee `routes/*` y `templates/*` para entender los flujos.

---
> Este README fue generado automáticamente como guía de traspaso — si quieres que escriba un `wsgi.py`, un script de init DB o añada ejemplos de `flask-migrate`, dímelo y lo preparo.
