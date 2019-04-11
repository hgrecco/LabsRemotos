
from flask import Flask, request, send_file, jsonify, Response
from .device import rangos, nombres, Oscilator, clip_between
from threading import Timer
from os import listdir, remove, path
from zipfile import ZipFile
from warnings import catch_warnings
import os


app = Flask(__name__)

API_KEY = '17a1240802ec4726fe6c8e174d144dbe3b5c4d05'
SESSION_TOKEN = '9363191fb9f973f9af3b0d1951b569ddbf3eacb2'

 # status_key = {0:'Todo OK', -1:'Valor inválido', -2:'Valor fuera de rango'}


# def require_api_key(view_function):
#     @wraps(view_function)
#     # the new, post-decoration function. Note *args and **kwargs here.
#     def decorated_function(*args, **kwargs):
#         if request.args.get('x-api-key') and request.args.get('x-api-key') == API_KEY:
#             return view_function(*args, **kwargs)
#         else:
#             return Response('El API Key es inválido', 401,
#                             {'WWWAuthenticate': 'Basic realm="Login Required"'})
#     return decorated_function
#
#
# def require_user_token(view_function):
#     @wraps(view_function)
#     # the new, post-decoration function. Note *args and **kwargs here.
#     def decorated_function(*args, **kwargs):
#         if request.args.get('x-user-token') and request.args.get('x-user-token') == USER_TOKEN:
#             return view_function(*args, **kwargs)
#         else:
#             return Response('El USER Token es inválido', 401,
#                             {'WWWAuthenticate': 'Basic realm="Login Required"'})
#     return decorated_function

dev = Oscilator(debug=False)

@app.route('/')
def index():
    return 'LVDF'

# # @app.before_request
# def _check():
#
#     valid_key = request.headers.get('x-api-key') and request.headers.get('x-api-key') == API_KEY
#     if not valid_key:
#         return Response('El API Key es inválido', 401,
#                         {'WWWAuthenticate': 'Basic realm="Login Required"'})
#
#     valid_token = request.headers.get('x-session-token') and request.headers.get('x-session-token') == SESSION_TOKEN
#     if not valid_token:
#         return Response('El session Token es inválido', 401,
#                         {'WWWAuthenticate': 'Basic realm="Login Required"'})
#

def cambiar_valor(parametro, valor, status=0):
    '''Intenta cambiar el el valor del parámetro dado. Si se levanta una
    advertencia, asume que es porque el valor estuvo fuera del rango dado
    y devuelve el valor correspondiente de status: -2. Faltaría chequear 
    qué warning se levantó.'''
    if valor is not None:
        with catch_warnings(record=True) as w:
            setattr(dev, parametro, valor)
            if w: #Es una lista vacía si no hubo warnings
                status = -2
    return status, getattr(dev, parametro)


def chequear_rango(parametro, valor, status=0):
    '''Chequea que el valor dado es´té en el rango adecuado, según el 
    parámetro. Si no lo está, avisa usando status=-2 y lo mete en el
    rango adecuado.'''
    with catch_warnings(record=True) as w:
        valor = clip_between(valor, *rangos[parametro])
        if w: #Es una lista vacía si no hubo warnings
            status = -2
    return status, valor


@app.route('/rangos')
def view_rangos():
    return jsonify(status=0, valor=rangos)


@app.route('/frecuencia')
@app.route('/frecuencia/<float:valor>')
@app.route('/frecuencia/<int:valor>')
def view_frecuencia(valor=None):
    status, valor_salida = cambiar_valor('frecuencia', valor)
    return jsonify(status=status, valor=valor_salida)


@app.route('/fase')
@app.route('/fase/<float:valor>')
@app.route('/fase/<int:valor>')
def view_fase(valor=None):
    status, valor_salida = cambiar_valor('fase', valor)
    return jsonify(status=status, valor=valor_salida)


@app.route('/amplitud')
@app.route('/amplitud/<float:valor>')
@app.route('/amplitud/<int:valor>')
def view_amplitud(valor=None):
    status, valor_salida = cambiar_valor('amplitud', valor)
    return jsonify(status=status, valor=valor_salida)


@app.route('/duracion')
@app.route('/duracion/<float:valor>')
@app.route('/duracion/<int:valor>')
def view_duracion(valor=None):
    status, valor_salida = cambiar_valor('duracion', valor)
    return jsonify(status=status, valor=valor_salida)


@app.route('/foto')
@app.route('/foto/<float:delay>')
@app.route('/foto/<int:delay>')
def view_foto(delay=None):

    if not delay:
        delay=1
    dev.snapshot(delay)
    return send_file('static/cuerda.jpg')


@app.route('/barrido/<int:duracion>/<int:frec_i>/<int:frec_f>')
@app.route('/barrido/<int:duracion>/<float:frec_i>/<int:frec_f>')
@app.route('/barrido/<int:duracion>/<int:frec_i>/<float:frec_f>')
@app.route('/barrido/<int:duracion>/<float:frec_i>/<float:frec_f>')
def hacer_barrido(duracion, frec_i, frec_f):

    # Chequeo que los valores estén en el rango admitido
    status, frec_i = chequear_rango('frecuencia', frec_i)
    status, frec_f = chequear_rango('frecuencia', frec_f, status)
    #status, duracion = chequear_rango('duracion', duracion, status)

    
    try:
        dev.video(duracion)
        dev.sweep(duracion, frec_i, frec_f)
        mandar = dict(file='video',
                         tiempo_estimado=duracion,
                         unidades='segundos',
                         barriendo_entre=[frec_i, frec_f])
        return jsonify(status=status, valor=mandar)
    except ValueError: #las frecuencias eran incompatibles
        msg = ('Valores de frecuencias incompatibles. Tal vez frec_i={} igual o más grande que '
            'frec_f={}, o ambas fuera del rango permitido, en cuyo caso frec_i=frec_f.'
            ).format(frec_i, frec_f)
        if status == -2:
            msg += '\n Frecuencias estaban fuera del rango permitido (status=-2).'
        return jsonify(status=-1, mensaje=msg)


@app.route('/fotos/<int:frec_i>/<int:frec_f>')
@app.route('/fotos/<int:frec_i>/<float:frec_f>')
@app.route('/fotos/<float:frec_i>/<int:frec_f>')
@app.route('/fotos/<float:frec_i>/<float:frec_f>')
def sacar_fotos(frec_i, frec_f):

    # Chequeo que los valores estén en el rango admitido
    status, frec_i = chequear_rango('frecuencia', frec_i)
    status, frec_f = chequear_rango('frecuencia', frec_f, status)

    try:
        dev.fotos(frec_i, frec_f)
        mandar = dict(file='timelapse',
                         tiempo_estimado=200, #mucho tiempo extra (debería tardar 100)
                         unidades='segundos',
                         barriendo_entre=[frec_i, frec_f])
        return jsonify(status=status, valor=mandar)
    except ValueError: #las frecuencias eran incompatibles
        msg = ('Valores de frecuencias incompatibles. Tal vez frec_i={} igual o más grande que '
            'frec_f={}, o ambas fuera del rango permitido, en cuyo caso frec_i=frec_f.'
            ).format(frec_i, frec_f)
        if status == -2:
            msg += '\n Frecuencias estaban fuera del rango permitido (status=-2).'
        return jsonify(status=-1, mensaje=msg)


@app.route('/ultima_foto')
def ultima_foto(delay=None):

    try:
        return send_file(nombres['foto'])
    except:
        msg = 'Archivo no existente.'
        return jsonify(status=-3, mensaje=msg)


@app.route('/getvideo')
def get_video():
    try:
        return send_file(nombres['video'])
    except:
        msg = 'Archivo no existente.'
        return jsonify(status=-3, mensaje=msg)


@app.route('/getfotos')
def get_fotos():
    base = dev.nombres['timelapse']
    lista = [os.path.join(base, f) for f in os.listdir(base)]

    if lista:
        dev.stop() #para que no siga creando fotos mientras intento mandarlas
        with ZipFile('send.zip', 'w') as zf:
            for f in lista:
                zf.write(f)
                remove(f)

        dev.play() #vuelvo a arrancar
        return send_file('send.zip')
    else:
        msg = 'Archivo no existente.'
        return jsonify(status=-3, mensaje=msg)


@app.route('/stop')
def stop():
    dev.stop()
    return jsonify(status=0)


@app.route('/play')
def play():
    dev.play()
    return jsonify(status=0)


def main(debug=True, browser=False, port=5000):
    if debug:
        print(os.getcwd())

    if browser:
        import threading, webbrowser
        url = "http://127.0.0.1:{0}".format(port)
        threading.Timer(3, lambda: webbrowser.open(url)).start()
    #app.run(port=port, debug=debug)
    app.run(host = '0.0.0.0', port=5000, debug=debug)
