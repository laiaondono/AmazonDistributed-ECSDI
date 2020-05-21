# -*- coding: utf-8 -*-
"""
Agente Buscador de productos.
Esqueleto de agente usando los servicios web de Flask

/comm es la entrada para la recepcion de mensajes del agente
/Stop es la entrada que para el agente

Tiene una funcion AgentBehavior1 que se lanza como un thread concurrente

Asume que el agente de registro esta en el puerto 9000

@author: pau-laia-anna
"""

from multiprocessing import Process, Queue
import socket

import flask
from rdflib import Namespace, Graph, RDF, Literal, URIRef
from flask import Flask, request, render_template

from Util.ACLMessages import build_message, send_message
from Util.FlaskServer import shutdown_server
from Util.Agent import Agent
from Util.OntoNamespaces import ONTO, ACL
from Util.Logging import config_logger

__author__ = 'pau-laia-anna'
logger = config_logger(level=1)

# Configuration stuff
hostname = socket.gethostname()

port = 9011

agn = Namespace("http://www.agentes.org#")

# Variables globales
mss_cnt = 0
products_list = []

# Datos del Agente

AgAsistente = Agent('AgAsistente',
                    agn.AgAsistente,
                    'http://%s:%d/comm' % (hostname, port),
                    'http://%s:%d/Stop' % (hostname, port))

AgBuscadorProductos = Agent('AgBuscadorProductos',
                            agn.AgBuscadorProductos,
                            'http://%s:9010/comm' % hostname,
                            'http://%s:9010/Stop' % hostname)

AgGestorCompra = Agent('AgGestorCompra',
                            agn.AgGestorCompra,
                            'http://%s:9012/comm' % hostname,
                            'http://%s:9012/Stop' % hostname)

# Directory agent address
DirectoryAgent = Agent('DirectoryAgent',
                       agn.Directory,
                       'http://%s:9000/Register' % hostname,
                       'http://%s:9000/Stop' % hostname)


# Global triplestore graph
dsgraph = Graph()

cola1 = Queue()

resultats = []

# Flask stuff
app = Flask(__name__, template_folder='../templates')


@app.route("/sum")
def suma():
    num1 = request.args['numero1']
    num2 = request.args['numero2']
    resultats.append(int(num1) + int(num2))
    return str(int(num1) + int(num2))


@app.route("/comm")
def comunicacion():
    """
    Entrypoint de comunicacion
    """
    global dsgraph
    global mss_cnt
    return str(resultats)


@app.route("/Stop")
def stop():
    """
    Entrypoint que para el agente

    :return:
    """
    tidyup()
    shutdown_server()
    return "Parando Servidor"


def tidyup():
    """
    Acciones previas a parar el agente
    """

    pass


@app.route("/search_products", methods=['GET', 'POST'])
def search_products():
    if request.method == 'GET':
        return render_template('busqueda_productos.html', products=None)
    else:
        if request.form['submit'] == 'Busca':
            global products_list
            name = request.form['name']
            minPrice = request.form['minPrice']
            maxPrice = request.form['maxPrice']
            brand = request.form['brand']
            products_list = buscar_productos(name, minPrice, maxPrice, brand)
            return flask.redirect("http://%s:%d/hacer_pedido" % (hostname, port))


def buscar_productos(name = None, minPrice = 0.0, maxPrice = 10000.0, brand = None):
    global mss_cnt, products_list
    g = Graph()

    action = ONTO['BuscarProductos_' + str(mss_cnt)]
    g.add((action, RDF.type, ONTO.BuscarProductos))

    if name:
        nameRestriction = ONTO['RestriccionNombre_' + str(mss_cnt)]
        g.add((nameRestriction, RDF.type, ONTO.RestriccionNombre))
        g.add((nameRestriction, ONTO.Nombre, Literal(name))) # datatype=XSD.string !??!!?!?!?
        g.add((action, ONTO.RestringidaPor, URIRef(nameRestriction)))

    if minPrice:
        minPriceRestriction = ONTO['RestriccionPrecio_' + str(mss_cnt)]
        g.add((minPriceRestriction, RDF.type, ONTO.RestriccionPrecio))
        g.add((minPriceRestriction, ONTO.PrecioMinimo, Literal(minPrice)))
        g.add((action, ONTO.RestringidaPor, URIRef(minPriceRestriction)))

    if maxPrice:
        maxPriceRestriction = ONTO['RestriccionPrecio_' + str(mss_cnt)]
        g.add((maxPriceRestriction, RDF.type, ONTO.RestriccionPrecio))
        g.add((maxPriceRestriction, ONTO.PrecioMaximo, Literal(maxPrice)))
        g.add((action, ONTO.RestringidaPor, URIRef(maxPriceRestriction)))

    if brand:
        brandRestriction = ONTO['RestriccionMarca_' + str(mss_cnt)]
        g.add((brandRestriction, RDF.type, ONTO.RestriccionMarca))
        g.add((brandRestriction, ONTO.Marca, Literal(brand))) # datatype=XSD.string !??!!?!?!?
        g.add((action, ONTO.RestringidaPor, URIRef(brandRestriction)))

    msg = build_message(g, ACL.request, AgAsistente.uri, AgBuscadorProductos.uri, action, mss_cnt)
    mss_cnt += 1
    gproducts = send_message(msg, AgBuscadorProductos.address)

    products_list = []
    subjects_position = {}
    pos = 0
    for s, p, o in gproducts:
        if s not in subjects_position:
            print(s)
            print(p)
            print(o)
            subjects_position[s] = pos
            pos += 1
            products_list.append({})
        if s in subjects_position:
            product = products_list[subjects_position[s]]
            if p == RDF.type:
                product['url'] = s
            if p == ONTO.Identificador:
                product['id'] = o
            if p == ONTO.Nombre:
                product['name'] = o
            if p == ONTO.Marca:
                product['brand'] = o
            if p == ONTO.Precio:
                product['price'] = o
    return products_list


@app.route("/hacer_pedido", methods=['GET', 'POST'])
def hacer_pedido():
    global products_list
    if request.method == 'GET':
        return render_template('nuevo_pedido.html', products=products_list, bill=None)
    else:
        if request.form['submit'] == 'Comprar':
            city = request.form['city']
            priority = request.form['priority']
            creditCard = request.form['creditCard']
            products_to_buy = []
            for p in request.form.getlist("checkbox"):
                prod = products_list[int(p)]
                # print("prod " + str(prod))
                product_checked = prod['url']
                # print("product_checked " + str(product_checked))
                products_to_buy.append(product_checked)
            return render_template('nuevo_pedido.html', products=None, bill=comprar_productos(products_to_buy, city, priority, creditCard))


def comprar_productos(products_to_buy, city, priority, creditCard):
    global mss_cnt
    g = Graph()
    action = ONTO['HacerPedido_' + str(mss_cnt)]
    g.add((action, RDF.type, ONTO.HacerPedido))

    cityonto = ONTO[city]
    g.add((cityonto, ONTO.Ciudad, Literal(city)))
    priorityonto = ONTO[city]
    g.add((priorityonto, ONTO.PrioridadEntrega, Literal(priority)))
    creditCardonto = ONTO[city]
    g.add((creditCardonto, ONTO.TargetaCredito, Literal(creditCard)))
    for p in products_to_buy:
        g.add((action, ONTO.ProductosPedido, p))
        # print(p)

    msg = build_message(g, ACL.request, AgAsistente.uri, AgGestorCompra.uri, action, mss_cnt)
    mss_cnt += 1
    gfactura = send_message(msg, AgGestorCompra.address)

    #rel productoscompra uriref productos, NumeroProductos, preciotitala
    products_bought = []
    """
    subjects_position = {}
    pos = 0
    msgdic = get_message_properties(g)
    content = msgdic['content']
    prods = gfactura.objects(content, ONTO.ProductosCompra)
    for s, p, o in gfactura:
        if s not in subjects_position:
            subjects_position[s] = pos
            pos += 1
            products_list.append({})
        if s in subjects_position:
            product = products_list[subjects_position[s]]
            if p == RDF.type:
                product['url'] = s
            if p == ONTO.Identificador:
                product['id'] = o
            if p == ONTO.Nombre:
                product['name'] = o
            if p == ONTO.Marca:
                product['brand'] = o
            if p == ONTO.Precio:
                product['price'] = o
    """
    return products_bought



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

    # Ponemos en marcha el servidor
    app.run(host=hostname, port=port)

    # Esperamos a que acaben los behaviors
    ab1.join()
    print('The End')
