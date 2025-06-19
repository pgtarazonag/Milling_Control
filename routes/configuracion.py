from flask import Blueprint, render_template, request, redirect, url_for, flash
from models import Configuracion
from extensions import db

configuracion_bp = Blueprint('configuracion', __name__, url_prefix='/configuracion')

@configuracion_bp.route('/', methods=['GET', 'POST'])
def configuracion():
    maquinas = Configuracion.get_lista('maquinas', default=['A','B','C','D'])
    materiales = Configuracion.get_lista('materiales', default=['Zirconia','Disilicato','PMMA','Cera','Wax','Composite'])
    shades = Configuracion.get_lista('shades', default=['A1','A2','A3','B1','B2','C1','C2'])
    marcas = Configuracion.get_lista('marcas', default=['Vita','Ivoclar','Aidite'])
    grosores = Configuracion.get_lista('grosores', default=['14','16','18','20','22','25'])
    hornos = Configuracion.get_lista('hornos', default=['Horno 1','Horno 2','Horno 3'])
    aspiradoras = Configuracion.get_lista('aspiradoras', default=['Aspiradora 1','Aspiradora 2','Aspiradora 3'])
    if request.method == 'POST':
        nuevas_maquinas = [m.strip() for m in request.form.get('maquinas','').split(',') if m.strip()]
        Configuracion.set_lista('maquinas', nuevas_maquinas)
        nuevos_hornos = [h.strip() for h in request.form.get('hornos','').split(',') if h.strip()]
        Configuracion.set_lista('hornos', nuevos_hornos)
        nuevos_aspiradoras = [a.strip() for a in request.form.get('aspiradoras','').split(',') if a.strip()]
        Configuracion.set_lista('aspiradoras', nuevos_aspiradoras)
        nuevos_materiales = [m.strip() for m in request.form.get('materiales','').split(',') if m.strip()]
        Configuracion.set_lista('materiales', nuevos_materiales)
        nuevos_shades = [s.strip() for s in request.form.get('shades','').split(',') if s.strip()]
        Configuracion.set_lista('shades', nuevos_shades)
        nuevas_marcas = [m.strip() for m in request.form.get('marcas','').split(',') if m.strip()]
        Configuracion.set_lista('marcas', nuevas_marcas)
        nuevos_grosores = [g.strip() for g in request.form.get('grosores','').split(',') if g.strip()]
        Configuracion.set_lista('grosores', nuevos_grosores)
        flash('Configuración actualizada correctamente.')
        return redirect(url_for('configuracion.configuracion'))
    return render_template('configuracion.html', maquinas=maquinas, materiales=materiales, shades=shades, marcas=marcas, grosores=grosores, hornos=hornos, aspiradoras=aspiradoras)
