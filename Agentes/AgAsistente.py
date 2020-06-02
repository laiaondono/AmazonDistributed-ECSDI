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

from Util.ACLMessages import *
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
global nombreusuario
nombreusuario = ""
global compra
compra = False
global grafo_respuesta
grafo_respuesta = Graph()
global info_bill
info_bill = {}
global completo
completo = False
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
AgProcesadorOpiniones = Agent('AgProcesadorOpiniones',
                       agn.AgProcesadorOpiniones,
                       'http://%s:9013/comm' % hostname,
                       'http://%s:9013/Stop' % hostname)

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
app = Flask(__name__,template_folder='../templates')

productes_a_valorar = {}


@app.route("/", methods=['GET', 'POST'])
def initialize():
    """
    Entrypoint de comunicacion
    """
    global nombreusuario

    if request.method == 'GET':
        if nombreusuario != "":
            return render_template('inicio.html', products=None, usuario= nombreusuario)
        else:
            return render_template('Username.html')

    else:

        if request.form['submit'] == 'search_products':
            return flask.redirect("http://%s:%d/search_products" % (hostname, port))
        elif request.form['submit'] == 'registro_usuario':
            nombreusuario = request.form['name']
            return  render_template('inicio.html', products=None, usuario=nombreusuario)
        else:
            return request.form['submit']


@app.route("/comm")
def comunicacion():
    """
    Entrypoint de comunicacion
    """
    message = request.args['content']
    gm = Graph()
    gm.parse(data=message)

    msgdic = get_message_properties(gm)

    gr = None
    global mss_cnt
    if msgdic is None:
        mss_cnt+=1
        # Si no es, respondemos que no hemos entendido el mensaje
        gr = build_message(Graph(), ACL['not-understood'], sender=AgAsistente.uri, msgcnt=str(mss_cnt))
    else:
        # Obtenemos la performativa
        if msgdic['performative'] != ACL.request:
            # Si no es un request, respondemos que no hemos entendido el mensaje
            gr = build_message(Graph(),
                               ACL['not-understood'],
                               sender=AgAsistente.uri,
                               msgcnt=str(mss_cnt))
        else:
            # Extraemos el objeto del contenido que ha de ser una accion de la ontologia
            # de registro
            content = msgdic['content']
            # Averiguamos el tipo de la accion
            accion = gm.value(subject=content, predicate=RDF.type)

            #Factura completa
            if accion == ONTO.ProcesarEnvio:
                global grafo_respuesta
                grafo_respuesta = gm
                global completo
                completo = True
                gr =Graph()
                return gr.serialize(format="xml"),200

            # Accion de valorar
            if accion == ONTO.ValorarProducto:
                gr =Graph()
                return gr.serialize(format="xml"),200




def hacer_redirect():
    return flask.redirect("http://%s:%d/" % (hostname, port))

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
    global nombreusuario
    if request.method == 'GET':
        return render_template('busqueda_productos.html', products=None, usuario=nombreusuario, busquedafallida=False)
    else:
        if request.form['submit'] == 'Busca':
            global products_list
            name = request.form['name']
            minPrice = request.form['minPrice']
            maxPrice = request.form['maxPrice']
            brand = request.form['brand']
            valoracion = request.form['valoracionminima']
            products_list = buscar_productos(name, minPrice, maxPrice, brand,valoracion)
            if len(products_list) == 0:
                return render_template('busqueda_productos.html', products=None, usuario=nombreusuario, busquedafallida=True)
            else:
                return flask.redirect("http://%s:%d/hacer_pedido" % (hostname, port))
        # TODO modificar html x si no hi ha cap producte que cumpleixi restriccions


def buscar_productos(name = None, minPrice = 0.0, maxPrice = 10000.0, brand = None, valoracion=0.0):
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
    if valoracion:
        RatingRestriction = ONTO['RestriccionValoracion_' + str(mss_cnt)]
        g.add((RatingRestriction, RDF.type, ONTO.RestriccionValoracion))
        g.add((RatingRestriction, ONTO.Valoracion, Literal(valoracion))) # datatype=XSD.string !??!!?!?!?
        g.add((action, ONTO.RestringidaPor, URIRef(RatingRestriction)))
    msg = build_message(g, ACL.request, AgAsistente.uri, AgBuscadorProductos.uri, action, mss_cnt)
    mss_cnt += 1
    gproducts = send_message(msg, AgBuscadorProductos.address)

    products_list = []
    subjects_position = {}
    pos = 0
    for s, p, o in gproducts:
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
            if p == ONTO.PrecioProducto:
                product['price'] = o
            if p == ONTO.Peso:
                product["weight"] = o
            if p == ONTO.Valoracion:
                product["rating"] = o
    return products_list


@app.route("/hacer_pedido", methods=['GET', 'POST'])
def hacer_pedido():
    global products_list
    if request.method == 'GET':
        # TODO ciudad, prioridad  (que nomes pot ser 1, 2 o 3)y tarjeta credit no pot estar buida
        return render_template('nuevo_pedido.html', products=products_list, bill=None,intento=False, completo =False,campos_error = False)
    else:
        if request.form['submit'] == 'Comprar':
            city = request.form['city']
            priority = request.form['priority']
            creditCard = request.form['creditCard']
            if city == "" or priority == "" or creditCard =="" or (priority != "1" and priority != "2" and priority != "3"):
                return render_template('nuevo_pedido.html', products=products_list, bill=None,intento=False, completo =False, campos_error = True)
            products_to_buy = []
            count = 0
            products_not_selected = []
            for p in request.form.getlist("checkbox"):
                products_not_selected.append(int(p))
                count+=1
                prod = products_list[int(p)]
                products_to_buy.append(prod)
            if count == 0:
                return render_template('nuevo_pedido.html', products=products_list, bill=None,intento=False, completo =False, campos_error = True)
            graph_historial = Graph();
            action = ONTO["ActualizarHistorial_"+ str(mss_cnt)]
            graph_historial.add((action, RDF.type, ONTO.ActualizarHistorial))
            usuario = ONTO["Usuario"]
            graph_historial.add((usuario,RDF.type,ONTO.Usuario))
            graph_historial.add((usuario,ONTO.DNI,Literal(nombreusuario)))
            graph_historial.add((action,ONTO.HistorialDe,URIRef(usuario)))
            count= 0
            for p in products_list:
                if not count in products_not_selected:
                    producto = ONTO["Producto_"+str(count)]
                    graph_historial.add((producto,RDF.type,ONTO.Producto))
                    graph_historial.add((producto,ONTO.Identificador,Literal(p["id"])))
                    graph_historial.add((producto,ONTO.Nombre,Literal(p["name"])))
                    graph_historial.add((action,ONTO.ProductosHistorial,URIRef(producto)))
                count+=1

            msg = build_message(graph_historial,ACL.request, AgAsistente.uri, AgProcesadorOpiniones.uri, action, mss_cnt)
            p = Process(target=send_message,args=(msg,AgProcesadorOpiniones.address))
            p.start()
            return render_template('nuevo_pedido.html', products=None, bill=comprar_productos(products_to_buy, city, priority, creditCard),intento=False, completo =False,campos_error = False)
        elif request.form['submit'] == "Visualizar datos completos":
            global completo
            global info_bill
            if not completo:
                return render_template('nuevo_pedido.html', products=None, bill=info_bill,intento=True, completo=False)
            else:
                global grafo_respuesta
                for s,p,o in grafo_respuesta:
                    if p == ONTO.FechaEntrega:
                        info_bill["FechaEntrega"]=str(o)[:16]
                    if p==ONTO.NombreTransportista:
                        info_bill["NombreTransportista"]=o
                return render_template('nuevo_pedido.html', products=None, bill=info_bill,intento=False, completo =True)
        elif request.form['submit'] == "Volver al inicio":
            return flask.redirect("http://%s:%d/" % (hostname, port))
        elif request.form['submit'] == 'Volver a buscar':
            graph_historial = Graph();
            action = ONTO["ActualizarHistorial_"+ str(mss_cnt)]
            graph_historial.add((action, RDF.type, ONTO.ActualizarHistorial))
            usuario = ONTO["Usuario"]
            graph_historial.add((usuario,RDF.type,ONTO.Usuario))
            graph_historial.add((usuario,ONTO.DNI,Literal(nombreusuario)))
            graph_historial.add((action,ONTO.HistorialDe,URIRef(usuario)))
            count= 0
            for p in products_list:
                count+=1
                producto = ONTO["Producto_"+str(count)]
                graph_historial.add((producto,RDF.type,ONTO.Producto))
                graph_historial.add((producto,ONTO.Identificador,Literal(p["id"])))
                graph_historial.add((producto,ONTO.Nombre,Literal(p["name"])))
                graph_historial.add((action,ONTO.ProductosHistorial,URIRef(producto)))

            msg = build_message(graph_historial,ACL.request, AgAsistente.uri, AgProcesadorOpiniones.uri, action, mss_cnt)
            p = Process(target=send_message,args=(msg,AgProcesadorOpiniones.address))
            p.start()
            return flask.redirect("http://%s:%d/search_products" % (hostname, port))



def comprar_productos(products_to_buy, city, priority, creditCard):
    global mss_cnt
    g = Graph()
    action = ONTO['HacerPedido_' + str(mss_cnt)]
    g.add((action, RDF.type, ONTO.HacerPedido))

    cityonto = ONTO[city]
    g.add((cityonto, ONTO.Ciudad, Literal(city)))
    g.add((action, ONTO.Ciudad, URIRef(cityonto)))

    priorityonto = ONTO[city]
    g.add((priorityonto, ONTO.PrioridadEntrega, Literal(priority)))
    g.add((action, ONTO.PrioridadEntrega, URIRef(priorityonto)))

    creditCardonto = ONTO[city]
    g.add((creditCardonto, ONTO.TarjetaCredito, Literal(creditCard)))
    g.add((action, ONTO.TarjetaCredito, URIRef(creditCardonto)))

    for p in products_to_buy:
        g.add((p['url'], RDF.type, ONTO.Producto))
        for atr in p:
            if (atr == "id"):
                g.add((p['url'], ONTO.Indentificador, p[atr]))
            elif (atr == "name"):
                g.add((p['url'], ONTO.Nombre, p[atr]))
            elif (atr == "url"):
                g.add((p['url'], ONTO.Indentificador, p[atr]))
            elif (atr == "brand"):
                g.add((p['url'], ONTO.Marca, p[atr]))
            elif (atr == "price"):
                g.add((p['url'], ONTO.PrecioProducto, p[atr]))
            elif (atr == "weight"):
                g.add((p['url'], ONTO.Peso, p[atr]))
        g.add((action, ONTO.ProductosPedido, p['url']))


    msg = build_message(g, ACL.request, AgAsistente.uri, AgGestorCompra.uri, action, mss_cnt)
    mss_cnt += 1
    gfactura = send_message(msg, AgGestorCompra.address)
    global info_bill
    info_bill = {}
    #LA FACTURA (info_bill) HA DE TENIR: city, prioridad, tar credit, array de noms de productes, preu total
    products_name = []
    for s, p, o in gfactura:
        if p == ONTO.Ciudad:
            info_bill['city'] = o
        if p == ONTO.PrioridadEntrega:
            info_bill['priority'] = o
        if p == ONTO.TarjetaCredito:
            info_bill['creditCard'] = o
        if p == ONTO.PrecioTotal:
            info_bill['price'] = o
        if p == ONTO.Nombre:
            products_name.append(o)
    info_bill['products'] = products_name

    return info_bill


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
