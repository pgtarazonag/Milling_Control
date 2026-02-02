from app import app
from extensions import db
from sqlalchemy import text

def run_migration():
    with app.app_context():
        try:
            # Check if table exists
            result = db.session.execute(text("SELECT name FROM sqlite_master WHERE type='table' AND name='log_inventario'")).fetchone()
            if result:
                print("Table 'log_inventario' already exists.")
            else:
                # Create table
                print("Creating table 'log_inventario'...")
                db.session.execute(text("""
                    CREATE TABLE log_inventario (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        fecha DATETIME,
                        accion VARCHAR(50),
                        bloque_id INTEGER,
                        descripcion VARCHAR(500),
                        detalles TEXT,
                        usuario VARCHAR(50)
                    )
                """))
                db.session.commit()
                print("Table 'log_inventario' created successfully.")
                
        except Exception as e:
            print(f"Error during migration: {e}")
            db.session.rollback()

if __name__ == '__main__':
    run_migration()
