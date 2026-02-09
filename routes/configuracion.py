from flask import Blueprint, render_template, request, redirect, url_for, flash
from models import Configuracion
from extensions import db
import json
import re

configuracion_bp = Blueprint('configuracion', __name__, url_prefix='/configuracion')

def normalize_key(s):
    return re.sub(r'[^a-zA-Z0-9]', '_', s)

@configuracion_bp.route('/', methods=['GET', 'POST'])
def configuracion():
    maquinas = Configuracion.get_lista('maquinas', default=['A','B','C','D'])
    materiales = Configuracion.get_lista('materiales', default=['Zirconia','Disilicato','PMMA','Cera','Wax','Composite'])
    shades = Configuracion.get_lista('shades', default=['A1','A2','A3','B1','B2','C1','C2'])
    marcas = Configuracion.get_lista('marcas', default=['Vita','Ivoclar','Aidite'])
    grosores = Configuracion.get_lista('grosores', default=['14','16','18','20','22','25'])
    hornos = Configuracion.get_lista('hornos', default=['Horno 1','Horno 2','Horno 3'])
    aspiradoras = Configuracion.get_lista('aspiradoras', default=['Aspiradora 1','Aspiradora 2','Aspiradora 3'])
    # Actividades de mantenimiento por grupo
    actividades_mant = Configuracion.get_lista('actividades_mantenimiento', default={
        'fresadoras': ['limpieza_general'],
        'hornos': ['calibracion_temperatura'],
        'aspiradoras': ['cambio_filtro']
    })
    if isinstance(actividades_mant, list) and actividades_mant and isinstance(actividades_mant[0], str) and actividades_mant[0].startswith('{'):
        actividades_mant = json.loads(actividades_mant[0])
    elif not isinstance(actividades_mant, dict):
        actividades_mant = {'fresadoras': [], 'hornos': [], 'aspiradoras': []}
    # Cargar configuración avanzada previa (si existe y es válida)
    try:
        materiales_avanzado = Configuracion.get_lista('materiales_avanzado')
        if isinstance(materiales_avanzado, dict):
            pass  # Ya es un dict válido
        elif materiales_avanzado and isinstance(materiales_avanzado, list) and isinstance(materiales_avanzado[0], str) and materiales_avanzado[0].startswith('{'):
            materiales_avanzado = json.loads(materiales_avanzado[0])
        else:
            materiales_avanzado = {}
    except Exception:
        materiales_avanzado = {}
    # Cargar asociación fresa-maquinas
    try:
        fresas_maquinas = Configuracion.get_lista('fresas_maquinas')
        if isinstance(fresas_maquinas, dict):
            pass
        elif fresas_maquinas and isinstance(fresas_maquinas, list) and isinstance(fresas_maquinas[0], str) and fresas_maquinas[0].startswith('{'):
            fresas_maquinas = json.loads(fresas_maquinas[0])
        else:
            fresas_maquinas = {}
    except Exception:
        fresas_maquinas = {}
    
    # Load reference code prefix for Excel exports
    ref_code_prefix = Configuracion.get_valor('ref_code_prefix', default='')
    
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
        # Guardar actividades de mantenimiento por grupo
        actividades_mant_post = {
            'fresadoras': [a.strip() for a in request.form.get('actividades_fresadoras','').replace('\r','').split('\n') if a.strip()],
            'hornos': [a.strip() for a in request.form.get('actividades_hornos','').replace('\r','').split('\n') if a.strip()],
            'aspiradoras': [a.strip() for a in request.form.get('actividades_aspiradoras','').replace('\r','').split('\n') if a.strip()]
        }
        Configuracion.set_lista('actividades_mantenimiento', [json.dumps(actividades_mant_post)])
        # Guardar configuración avanzada de materiales
        materiales_avanzado_post = {}
        for m in nuevos_materiales:
            norm = normalize_key(m)
            shades_key = f'shades_{norm}'
            marcas_key = f'marcas_{norm}'
            shades_val = [s.strip() for s in request.form.get(shades_key, '').split(',') if s.strip()]
            # --- NUEVO: Soporte para letra y color por marca ---
            marcas_val_raw = [s.strip() for s in request.form.get(marcas_key, '').split(',') if s.strip()]
            marcas_val = []
            for idx, marca_nombre in enumerate(marcas_val_raw):
                letra = request.form.get(f'letra_{norm}_{idx}', 'X') or 'X'
                color = request.form.get(f'color_{norm}_{idx}', '#000000') or '#000000'
                marcas_val.append({'nombre': marca_nombre, 'letra': letra, 'color': color})
            materiales_avanzado_post[m] = {'shades': shades_val, 'marcas': marcas_val}
        # Asegurar que todos los materiales tengan shades y marcas aunque sean vacíos
        for m in nuevos_materiales:
            if m not in materiales_avanzado_post:
                materiales_avanzado_post[m] = {'shades': [], 'marcas': []}
        Configuracion.set_lista('materiales_avanzado', [json.dumps(materiales_avanzado_post)])
        # Guardar asociación fresa-maquinas
        tipos_fresa = [f.strip() for f in request.form.get('tipos_fresa','').split(',') if f.strip()]
        fresas_maquinas_post = {}
        for f in tipos_fresa:
            norm = normalize_key(f)
            maquinas_key = f'maquinas_fresa_{norm}'
            maquinas_val = request.form.getlist(maquinas_key)
            fresas_maquinas_post[f] = maquinas_val
        Configuracion.set_lista('fresas_maquinas', [json.dumps(fresas_maquinas_post)])
        # Save reference code prefix
        ref_code_prefix = request.form.get('ref_code_prefix', '').strip()
        Configuracion.set_valor('ref_code_prefix', ref_code_prefix)
        flash('Configuración actualizada correctamente.')
        return redirect(url_for('configuracion.configuracion'))
    # Al mostrar el formulario, asegurar que todos los materiales tengan shades y marcas aunque sean vacíos
    for m in materiales:
        if m not in materiales_avanzado:
            materiales_avanzado[m] = {'shades': [], 'marcas': []}
    # --- NUEVO: Backward compatibility y valores por defecto para marcas ---
    for m in materiales:
        marcas = materiales_avanzado[m].get('marcas', [])
        # Si es lista de strings, migrar a objetos
        if marcas and isinstance(marcas[0], str):
            materiales_avanzado[m]['marcas'] = [
                {'nombre': nombre, 'letra': 'X', 'color': '#000000'} for nombre in marcas
            ]
        # Si es lista de objetos, asegurar que cada marca tenga los campos correctos
        for marca in materiales_avanzado[m]['marcas']:
            if 'nombre' not in marca or not marca['nombre']:
                marca['nombre'] = 'SinNombre'
            if 'letra' not in marca or not marca['letra']:
                marca['letra'] = 'X'
            if 'color' not in marca or not marca['color']:
                marca['color'] = '#000000'
    return render_template(
        'configuracion.html',
        maquinas=maquinas,
        materiales=materiales,
        shades=shades,
        marcas=marcas,
        grosores=grosores,
        hornos=hornos,
        aspiradoras=aspiradoras,
        materiales_avanzado=materiales_avanzado,
        fresas_maquinas=fresas_maquinas,
        normalize_key=normalize_key,
        actividades_mant=actividades_mant,
        ref_code_prefix=ref_code_prefix
    )
