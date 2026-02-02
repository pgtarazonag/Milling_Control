import sqlite3
import os

DB_PATH = 'instance/dental_lab.db'

def run_migration():
    if not os.path.exists(DB_PATH):
        print(f"Database not found at {DB_PATH}")
        return

    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        
        # Check if table exists
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='log_inventario'")
        if cursor.fetchone():
            print("Table 'log_inventario' already exists.")
        else:
            print("Creating table 'log_inventario'...")
            cursor.execute("""
                CREATE TABLE log_inventario (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    fecha TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    accion VARCHAR(50),
                    bloque_id INTEGER,
                    descripcion VARCHAR(500),
                    detalles TEXT,
                    usuario VARCHAR(50)
                )
            """)
            conn.commit()
            print("Table 'log_inventario' created successfully.")
            
        conn.close()
    except Exception as e:
        print(f"Error: {e}")

if __name__ == '__main__':
    run_migration()
