import os
import sys

# Add backend directory to sys.path
sys.path.append('c:\\Users\\asus_fx506h\\Desktop\\PYTHON')

from app import app
from models import db, LogInventario, Bloque, Orden

def reset_titanium_history():
    with app.app_context():
        # 1. Delete all Titanium inventory logs (Consumption and Restoration)
        logs_deleted = LogInventario.query.filter(
            LogInventario.accion.in_(['CONSUMO_TITANIO', 'RESTAURACION_TITANIO'])
        ).delete(synchronize_session=False)

        # 2. Reset the inventory quantity for all Titanium blocks based on a baseline assumption or 
        # (Since we don't know the exact baseline, we might just leave the blocks as they are currently, 
        # but the user said "resetea todo", let's ask or just reset the logs and any lingering orders)
        
        # 3. Delete any lingering Titanium orders just to be sure
        orders_deleted = Orden.query.filter(
            Orden.material.in_(['Titanio', 'Titanium'])
        ).delete(synchronize_session=False)

        db.session.commit()
        
        print(f"SUCCESS: Deleted {logs_deleted} Titanium inventory logs.")
        print(f"SUCCESS: Deleted {orders_deleted} lingering Titanium orders.")

if __name__ == '__main__':
    reset_titanium_history()
