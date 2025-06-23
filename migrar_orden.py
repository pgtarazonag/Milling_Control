from app import create_app
from extensions import db
from models import Orden

app = create_app()

with app.app_context():
    print('Eliminando registros de la tabla Orden...')
    db.session.query(Orden).delete()
    db.session.commit()
    print('Eliminando y recreando la tabla Orden...')
    Orden.__table__.drop(db.engine)
    Orden.__table__.create(db.engine)
    print('¡Listo! La tabla Orden fue migrada y las demás tablas no se tocaron.')
