from app import create_app
from extensions import db
from sqlalchemy import text

app = create_app()
with app.app_context():
    print("Starting database schema migration...")
    try:
        # Alter 'shade' columns to accept 255 characters
        db.session.execute(text("ALTER TABLE orden ALTER COLUMN shade TYPE VARCHAR(255);"))
        db.session.execute(text("ALTER TABLE bloque ALTER COLUMN shade TYPE VARCHAR(255);"))
        db.session.execute(text("ALTER TABLE bloque_historial ALTER COLUMN shade TYPE VARCHAR(255);"))
        
        # Ensure 'codigos_caso' is TEXT
        db.session.execute(text("ALTER TABLE orden ALTER COLUMN codigos_caso TYPE TEXT;"))
        db.session.commit()
        print("Successfully expanded column lengths.")
    except Exception as e:
        db.session.rollback()
        print(f"Error during migration: {e}")
