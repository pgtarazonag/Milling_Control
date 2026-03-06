import psycopg2
import sys

# Append backend to path so we can import app properly
sys.path.append('c:\\Users\\asus_fx506h\\Desktop\\PYTHON')

try:
    from app import app
    db_url = app.config['SQLALCHEMY_DATABASE_URI']
    
    conn = psycopg2.connect(db_url)
    cur = conn.cursor()
    
    # 1. Delete all Titanium Orders
    cur.execute("DELETE FROM orden WHERE material IN ('Titanio', 'Titanium');")
    orders_deleted = cur.rowcount
    
    # 2. Delete all Titanium Logs
    cur.execute("DELETE FROM log_inventario WHERE accion IN ('CONSUMO_TITANIO', 'RESTAURACION_TITANIO');")
    logs_deleted = cur.rowcount
    
    conn.commit()
    print(f"SUCCESS: Wiped {orders_deleted} lingering Titanium orders.")
    print(f"SUCCESS: Wiped {logs_deleted} Titanium inventory logs.")
    
    cur.close()
    conn.close()

except Exception as e:
    print(f"Failed pulling URL from app: {e}")
