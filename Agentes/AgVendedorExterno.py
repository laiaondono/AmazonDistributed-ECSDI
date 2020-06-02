# -*- coding: utf-8 -*-
"""
Agente Gestor de Compra.
Esqueleto de agente usando los servicios web de Flask

/comm es la entrada para la recepcion de mensajes del agente
/Stop es la entrada que para el agente

Tiene una funcion AgentBehavior1 que se lanza como un thread concurrente

Asume que el agente de registro esta en el puerto 9000

@author: pau-laia-anna
"""
import socket
from multiprocessing import Process, Queue
from flask import Flask, request, render_template
from rdflib import Namespace, Graph, RDF, Literal, URIRef, XSD

from Util.ACLMessages import *
from Util.Agent import Agent
from Util.Logging import config_logger
from Util.OntoNamespaces import ONTO, ACL

from datetime import datetime
import time
from Util.FlaskServer import shutdown_server

__author__ = 'pau-laia-anna'
logger = config_logger(level=1)

# Configuration stuff
hostname = socket.gethostname()
port = 9018

agn = Namespace("http://www.agentes.org#")

# Contador de mensajes
mss_cnt = 7 # tenim 6 productes externs afegits per defecte
# Datos del Agente
numeros_cuenta = {'Nike':"ESBN00909191",'IKEA':"ESBN0123442212",'Apple':"ESBN91120302102"}
AgVendedorExterno = Agent('AgVendedorExterno',
                    agn.AgVendedorExterno,
                    'http://%s:%d/comm' % (hostname, port),
                    'http://%s:%d/Stop' % (hostname, port))

AgGestorProductos = Agent('AgGestorProductos',
                       agn.AgGestorProductos,
                       'http://%s:9017/comm' % hostname,
                       'http://%s:9017/Stop' % hostname)

# Global triplestore graph
dsgraph = Graph()

cola1 = Queue()

# Flask stuff
app = Flask(__name__, template_folder='../templates')


errorsList = ["no", "no", "no", "no"]

def get_count():
    global mss_cnt
    mss_cnt += 1
    return mss_cnt


@app.route("/", methods=['GET', 'POST'])
def add_product():
    no_errors=["no", "no", "no", "no"]
    if request.method == 'GET':
        return render_template('nuevo_producto_externo.html', start = True, errors = no_errors)
    else:
        if request.form['submit'] == 'Añadir':
            global products_list
            companyName = request.form['companyName']
            productName = request.form['productName']
            price = request.form['price']
            brand = request.form['brand']
            category = request.form['category'] #TODO aixo no es correcteeeee
            weight = request.form['weight']
            global errorsList
            errorsList = ["no", "no", "no", "no"]
            product_added = add_new_product(companyName, productName, price, brand, category, weight)
            return render_template('nuevo_producto_externo.html', start = product_added, errors = errorsList)
        if request.form['submit'] == 'Volver':
            return render_template('nuevo_producto_externo.html', start = True, errors = no_errors)


def add_new_product(companyName, productName, price, brand, category, weight):
    global mss_cnt, errorsList
    g = Graph()
    cnt = get_count()

    error = False
    if not companyName or not productName or not price or not brand or not category or not weight:
        errorsList[0] = "si"
        error = True
        return True

    if companyName != "Ikea" and companyName != "Apple" and companyName != "Nike":
        errorsList[1] = "si"
        error = True
    if not price.replace('.', '', 1).isdigit():
        errorsList[2] = "si"
        error = True
    if not weight.replace('.', '', 1).isdigit():
        errorsList[3] = "si"
        error = True

    if error:
        return True

    action = ONTO['AñadirProductoExterno_' + str(cnt)]
    g.add((action, RDF.type, ONTO.AñadirProductoExterno))

    productNameSubject = ONTO['ProductoEX_' + str(cnt)]
    g.add((productNameSubject, RDF.type, ONTO.Producto))
    g.add((action, ONTO.Añade, productNameSubject))

    g.add((action, ONTO.Nombre, Literal(companyName)))
    g.add((productNameSubject, ONTO.Nombre, Literal(productName)))
    g.add((productNameSubject, ONTO.PrecioProducto, Literal(price)))
    g.add((productNameSubject, ONTO.Marca, Literal(brand)))
    g.add((productNameSubject, ONTO.Peso, Literal(weight)))
    g.add((productNameSubject, ONTO.Categoria, Literal(category)))

    msg = build_message(g, ACL.request, AgVendedorExterno.uri, AgGestorProductos.uri, action, get_count())
    send_message(msg, AgGestorProductos.address)
    return False


@app.route("/comm")
def communication():
    """
    Communication Entrypoint
    """
    message = request.args['content']
    gm = Graph()
    gm.parse(data=message)

    msgdic = get_message_properties(gm)

    gr = None
    if msgdic is None:
        # Si no es, respondemos que no hemos entendido el mensaje
        gr = build_message(Graph(), ACL['not-understood'], sender=AgVendedorExterno.uri, msgcnt=get_count())
    else:
        # Obtenemos la performativa
        if msgdic['performative'] != ACL.request:
            # Si no es un request, respondemos que no hemos entendido el mensaje
            gr = build_message(Graph(),
                               ACL['not-understood'],
                               sender=AgVendedorExterno.uri,
                               msgcnt=get_count())
        else:
            # Extraemos el objeto del contenido que ha de ser una accion de la ontologia
            # de registro
            content = msgdic['content']
            # Averiguamos el tipo de la accion
            accion = gm.value(subject=content, predicate=RDF.type)
            nombre_empresa = ""
            if accion == ONTO.PagarVendedorExterno:
                for s,p,o in gm:
                    if p == ONTO.Nombre:
                        nombre_empresa = str(o)
                        break
                graphrespuesta = Graph()
                accion=ONTO["PagarVendedorExterno"]
                graphrespuesta.add((accion,RDF.type,ONTO.PagarVendedorExterno))
                if nombre_empresa != "Nike" and nombre_empresa != "IKEA" and nombre_empresa != "Apple":
                    return graphrespuesta.serialize(format='xml'),200
                elif accion == ONTO.AvisarEnvio:
                    g = Graph()
                    action = ONTO["AvisarEnvio_" + str(get_count())]
                    g.add((action, RDF.type, ONTO.AvisarEnvio))
                    print("recibidooooo")
                    return g.serialize(format="xml"),200
                else:
                    global numeros_cuenta
                    graphrespuesta.add((accion,ONTO.NumeroCuenta,Literal(numeros_cuenta[str(nombre_empresa)])))
                    return graphrespuesta.serialize(format='xml'),200





            # Accion de busqueda
        # if accion == ONTO.HacerPedido:
    return "Este agente se encargará de añadir productos."


def agentbehavior1(queue):
    """
    Un comportamiento del agente
    :return:
    """
    pass


if __name__ == '__main__':
    # Ponemos en marcha los behaviors
    ab1 = Process(target=agentbehavior1, args=(cola1,))
    ab1.start()
    compra =False
    # Ponemos en marcha el servidor
    app.run(host=hostname, port=port)

    # Esperamos a que acaben los behaviors
    ab1.join()

    ('The End')