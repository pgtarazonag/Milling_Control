import sqlite3
import os

# Database file path
DB_PATH = 'instance/fresado.db'

def migrate():
    if not os.path.exists(DB_PATH):
        print(f"Error: Database file not found at {DB_PATH}")
        return

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    tables = ['bloque', 'bloque_historial']
    column_name = 'codigo_referencia'

    for table in tables:
        try:
            # Check if column exists
            cursor.execute(f"PRAGMA table_info({table})")
            columns = [info[1] for info in cursor.fetchall()]
            
            if column_name in columns:
                print(f"Column '{column_name}' already exists in table '{table}'.")
            else:
                print(f"Adding column '{column_name}' to table '{table}'...")
                cursor.execute(f"ALTER TABLE {table} ADD COLUMN {column_name} VARCHAR(100)")
                conn.commit()
                print(f"Successfully updated '{table}'.")
        except Exception as e:
            print(f"Error updating table '{table}': {e}")

    conn.close()

if __name__ == '__main__':
    migrate()
