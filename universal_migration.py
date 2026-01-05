from app import create_app
from extensions import db
from sqlalchemy import text

def run_migration():
    log_file = "migration_report.txt"
    with open(log_file, "w") as f:
        def log(msg):
            print(msg)
            f.write(msg + "\n")
            
        app = create_app()
        with app.app_context():
            db_url = str(db.engine.url)
            log(f"Connecting to database with scheme: {db_url.split(':')[0]}")
            
            migrations = [
                ('mantenimiento', 'proxima_fecha', 'TIMESTAMP'),
                ('bloque', 'codigo_referencia', 'VARCHAR(100)'),
                ('bloque_historial', 'codigo_referencia', 'VARCHAR(100)')
            ]
            
            for table, column, col_type in migrations:
                log(f"-- Processing {table}.{column} --")
                try:
                    db.session.execute(text(f"SELECT {column} FROM {table} LIMIT 1"))
                    log(f"SUCCESS: Column '{column}' already exists in '{table}'.")
                except Exception as e:
                    db.session.rollback()
                    log(f"INFO: Column '{column}' missing in '{table}'. Attempting to add...")
                    try:
                        db.session.execute(text(f"ALTER TABLE {table} ADD COLUMN {column} {col_type}"))
                        db.session.commit()
                        log(f"SUCCESS: Added '{column}' to '{table}'.")
                    except Exception as e2:
                        db.session.rollback()
                        log(f"ERROR: Failed to add '{column}' to '{table}': {e2}")
                log("-" * 20)
            log("MIGRATION PROCESS FINISHED")

if __name__ == '__main__':
    run_migration()
