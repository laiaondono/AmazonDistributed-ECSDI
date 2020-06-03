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
import random
import socket
import string
from multiprocessing import Queue, Process
from flask import Flask, request
from pyparsing import Literal
import requests
from rdflib import Namespace, Graph, RDF, Literal, URIRef, XSD

#from Agentes import AgCentroLogistico
from Util.ACLMessages import *
from Util.Agent import Agent
from Util.Logging import config_logger
from Util.OntoNamespaces import ONTO, ACL
from opencage.geocoder import OpenCageGeocode
from geopy.geocoders import Nominatim
from geopy.distance import geodesic, great_circle
from geopy import geocoders

from datetime import datetime
import time
from Util.FlaskServer import shutdown_server

__author__ = 'pau-laia-anna'
logger = config_logger(level=1)

# Configuration stuff
hostname = socket.gethostname()
port = 9012

agn = Namespace("http://www.agentes.org#")

# Contador de mensajes
mss_cnt = 0
# Datos del Agente

AgGestorCompra = Agent('AgGestorCompra',
                       agn.AgGestorCompra,
                       'http://%s:%d/comm' % (hostname, port),
                       'http://%s:%d/Stop' % (hostname, port))

# Directory agent address
DirectoryAgent = Agent('DirectoryAgent',
                       agn.Directory,
                       'http://%s:9000/Register' % hostname,
                       'http://%s:9000/Stop' % hostname)

# Directory agent address
AgAsistente = Agent('AgAsistente',
                    agn.AgAsistente,
                    'http://%s:9011/comm' % hostname,
                    'http://%s:9011/Stop' % hostname)

AgProcesadorPedidos = Agent('AgAsistente',
                            agn.AgAsistente,
                            'http://%s:9013/Register' % hostname,
                            'http://%s:9013/Stop' % hostname)

AgCentroLogistico = Agent('AgCentroLogistico',
                          agn.AgCentroLogistico,
                          'http://%s:9014/comm' % hostname,
                          'http://%s:9014/Stop' % hostname)

AgProcesadorOpiniones = Agent('AgProcesadorOpiniones',
                          agn.AgProcesadorOpiniones,
                          'http://%s:9013/comm' % hostname,
                          'http://%s:9013/Stop' % hostname)

AgServicioPago = Agent('AgServicioPago',
                       agn.AgServicioPago,
                       'http://%s:9019/comm' % hostname,
                       'http://%s:9019/Stop' % hostname)

# Global triplestore graph
dsgraph = Graph()

cola1 = Queue()

# Flask stuff
app = Flask(__name__)

location_ny = (Nominatim(user_agent='myapplication').geocode("New York").latitude,
               Nominatim(user_agent='myapplication').geocode("New York").longitude)
location_bcn = (Nominatim(user_agent='myapplication').geocode("Barcelona").latitude,
                Nominatim(user_agent='myapplication').geocode("Barcelona").longitude)
location_pk = (Nominatim(user_agent='myapplication').geocode("Pekín").latitude,
               Nominatim(user_agent='myapplication').geocode("Pekín").longitude)

graph_compra = Graph()
precio_total_compra = 0.0


def get_count():
    global mss_cnt
    mss_cnt += 1
    return mss_cnt


@app.route("/comm")
def communication():
    """
    Communication Entrypoint
    """
    message = request.args['content']
    gm = Graph()
    gm.parse(data=message)

    msgdic = get_message_properties(gm)
    global graph_compra
    global precio_total_compra
    gr = None
    if msgdic is None:
        # Si no es, respondemos que no hemos entendido el mensaje
        gr = build_message(Graph(), ACL['not-understood'], sender=AgAsistente.uri, msgcnt=get_count())
    else:
        # Obtenemos la performativa
        if msgdic['performative'] != ACL.request:
            # Si no es un request, respondemos que no hemos entendido el mensaje
            gr = build_message(Graph(),
                               ACL['not-understood'],
                               sender=AgAsistente.uri,
                               msgcnt=get_count())
        else:
            # Extraemos el objeto del contenido que ha de ser una accion de la ontologia
            # de registro
            content = msgdic['content']
            # Averiguamos el tipo de la accion
            accion = gm.value(subject=content, predicate=RDF.type)
            # Accion de busqueda
            if accion == ONTO.HacerPedido:
                #guardem el graf de la compra com a variable global
                global graph_compra
                graph_compra = gm

                # Llega una nueva peticion de una compra. Primero generamos la factura.
                numero_productos = 0
                precio_total = 0.0
                graffactura = Graph()
                # Llamamos a get_count para generar un numero de factura.
                count = 0
                PedidosFile = open('../Data/RegistroPedidos')
                graphfinal = Graph()
                graphfinal.parse(PedidosFile, format='turtle')
                for s,p,o in graphfinal:
                    if p == ONTO.Lote:
                        count+=1
                count_real = count
                count = str(count)
                # Generamos la factura
                factura = ONTO["Factura_" + count]
                accion = ONTO["EnviarFactura_" + count]
                # Añadimos al grafo la accion enviar factura, y referenciamos la factura con la URIRef.
                graffactura.add((accion, RDF.type, ONTO.EnviarFactura))
                graffactura.add((accion, ONTO.FacturaEnviada, URIRef(factura)))
                # Añadimos al grafo un objecto factura, en el que añadiremos cosas.
                graffactura.add((factura, RDF.type, ONTO.Factura))
                for s,p,o in gm:
                    if p==ONTO.DNI:
                        dni_usuari = str(o)
                ciudad = gm.objects(content, ONTO.Ciudad)
                for c in ciudad:
                    city = gm.value(subject=c, predicate=ONTO.Ciudad)
                    # Añadimos el atributo ciudad en la factura.
                    graffactura.add((factura, ONTO.Ciudad, Literal(city)))
                    break

                prioridad = gm.objects(content, ONTO.PrioridadEntrega)
                for p in prioridad:
                    priority = gm.value(subject=p, predicate=ONTO.PrioridadEntrega)
                    # Añadimos el atributo Prioridad de Entrega en la factura.
                    graffactura.add((factura, ONTO.PrioridadEntrega, Literal(priority)))
                    break

                tarjcred = gm.objects(content, ONTO.TarjetaCredito)
                for t in tarjcred:
                    creditCard = gm.value(subject=t, predicate=ONTO.TarjetaCredito)
                    # Añadimos el atributo Tarjeta de credito en la factura.
                    graffactura.add((factura, ONTO.TarjetaCredito, Literal(creditCard)))
                    break

                productos = gm.objects(content, ONTO.ProductosPedido)
                for producto in productos:
                    numero_productos += 1
                    precio_total += float(gm.value(subject=producto, predicate=ONTO.PrecioProducto))
                    # Generamos un nuevo objeto producto y lo añadimos a la relacion ProductosFactura
                    nombreProd = gm.value(subject=producto, predicate=ONTO.Nombre)
                    nomSuj = gm.value(predicate=ONTO.Nombre, object=nombreProd)
                    graffactura.add((nomSuj, RDF.type, ONTO.Producto))
                    graffactura.add((nomSuj, ONTO.Nombre, nombreProd))
                    graffactura.add((factura, ONTO.ProductosFactura, URIRef(nomSuj)))

                # Añadimos el precio total y el numero de productos en la factura.
                graffactura.add((factura, ONTO.NumeroProductos, Literal(numero_productos)))
                graffactura.add((factura, ONTO.PrecioTotal, Literal(precio_total)))
                graffactura.add((factura,ONTO.DNI,Literal(dni_usuari)))

                # Empezamos a procesar la compra mientras se devuelve la factura
                empezar_proceso = Process(target=procesar_compra, args=(
                    count_real, graffactura, gm, precio_total, content, priority, creditCard,dni_usuari))
                empezar_proceso.start()
                return graffactura.serialize(format='xml'), 200

            #AgServicioPago ens avisa que ja ha realitzat el cobro i aixi podem realitzar la valoracio
            if accion == ONTO.CobrarCompra:
                g = Graph()
                g.add((accion, RDF.type, ONTO.CobrarCompra))
                for s, p, o in graph_compra:
                    if p == ONTO.ProductosCompra:
                        g.add((accion, ONTO.ProductosCompra, o))
                    if p == ONTO.TarjetaCredito:
                        g.add((accion, ONTO.TarjetaCredito, o))
                    if p == ONTO.DNI:
                        g.add((accion, ONTO.DNI, o))
                g.add((accion, ONTO.PrecioTotal, Literal(precio_total_compra)))
                lote = gm.value(subject=accion, predicate=ONTO.LoteEntregado)
                for s, p, o in gm:
                    if p == ONTO.LoteEntregado:
                        lote = str(o)
                        print("lote torbat")
                g.add((accion, ONTO.LoteEntregado, Literal(lote)))
                print("cobar compra gc")
                for s, p, o in g:
                    print(s)
                    print(p)
                    print(o)

                msg = build_message(g, ACL.request, AgGestorCompra.uri, AgServicioPago.uri, accion, get_count())
                send_message(msg, AgServicioPago.address)
                # Avisamos al AgProcessadorOpiniones de que ya se puede realizar la valoracion
                empezar_proceso = Process(target=avisar_valoracion, args=())
                empezar_proceso.start()

                #Returnem ACK al AgServicioPago conforme ho hem rebut
                grr = Graph()
                return grr.serialize(format="xml"),200

def avisar_valoracion():
    global graph_compra

    # Avisar al AgProcesadorOpiniones que ja pot valorar els productes del graf.
    graph_valoracio = Graph()

    accion = ONTO["ValorarProducto" + str(get_count())]
    graph_valoracio.add((accion, RDF.type, ONTO.ValorarProducto))

    msgdic = get_message_properties(graph_compra)
    content = msgdic['content']

    productos = graph_compra.objects(content, ONTO.ProductosPedido)
    for producto in productos:
        # Generamos un nuevo objeto producto y lo añadimos a la relacion
        nombreProd = graph_compra.value(subject=producto, predicate=ONTO.Nombre)
        nomSuj = graph_compra.value(predicate=ONTO.Nombre, object=nombreProd)
        graph_valoracio.add((nomSuj, RDF.type, ONTO.Producto))
        graph_valoracio.add((nomSuj, ONTO.Nombre, nombreProd))
        graph_valoracio.add((accion, ONTO.ProductosValoracion, URIRef(nomSuj)))

    msg = build_message(graph_valoracio, ACL.request, AgGestorCompra.uri, AgProcesadorOpiniones.uri, accion, get_count())
    send_message(msg, AgProcesadorOpiniones.address)
    return



def procesar_compra(count=0.0, factura=Graph(), gm=Graph(), preutotal=0.0, content="", prioridad=0, tarjeta="",dni=""):
    logger.info("Procesando compra...")
    city = ""
    # Obtenemos la ciudad de destino
    ciudad = gm.objects(content, ONTO.Ciudad)
    for c in ciudad:
        city = gm.value(subject=c, predicate=ONTO.Ciudad)
    # Calculamos que Centro Logistico asignar a la compra.
    geolocator = Nominatim(user_agent='myapplication')
    location = geolocator.geocode(city)
    location = (location.latitude, location.longitude)
    dist_fromny = great_circle(location_ny, location).km
    dist_frompk = great_circle(location_pk, location).km
    dist_frombcn = great_circle(location_bcn, location).km
    if dist_frombcn < dist_fromny and dist_frombcn < dist_frompk:
        logger.info("El Centro Logistico de Barcelona se encargará de la compra_" + str(count))
        # request_envio("Barcelona", gm)
        centro = "Barcelona"
    elif dist_frompk < dist_fromny and dist_frompk < dist_frombcn:
        logger.info("El Centro Logistico de Pekín se encargará de la compra_" + str(count))
        # request_envio("Pekin", gm)
        centro = "Pekin"
    else:
        logger.info("El Centro Logistico de Nueva York se encargará de la compra_" + str(count))
        # request_envio("New York", gm)
        centro = "New York"
    # Empezamos a crear el grafo con la información de la compra para que el CentroLogístico pueda enviar la compra.
    accion = ONTO["ProcesarEnvio_" + str(count)]
    graph = Graph()
    compra = ONTO["Compra_" + str(count)]
    # El grafo tiene la accion enviar paquete. En esta accion tiene que constar la relacion Envia, que relaciona el envio con la compra.
    graph.add((accion, RDF.type, ONTO.ProcesarEnvio))
    # Generamos una compra que constará en el grafo. Primero añadimos atributos basicos.
    graph.add((compra,RDF.type,ONTO.Compra))
    graph.add((compra, ONTO.Ciudad, Literal(city, datatype=XSD.string)))
    graph.add((compra, ONTO.Identificador, Literal(compra, datatype=XSD.string)))
    graph.add((compra, ONTO.PrecioTotal, Literal(preutotal, datatype=XSD.float)))
    graph.add((compra, ONTO.PrioridadEntrega, Literal(prioridad, datatype=XSD.float)))
    graph.add((compra, ONTO.TarjetaCredito, Literal(tarjeta, datatype=XSD.string)))
    # Añadimos los datos de los productos.
    productos = gm.objects(content, ONTO.ProductosPedido)
    for producto in productos:
        # Generamos un objeto producto y le asignamos atributos.
        nombreProd = gm.value(subject=producto, predicate=ONTO.Nombre)
        nomSuj = gm.value(predicate=ONTO.Nombre, object=nombreProd)
        peso = gm.value(subject=producto, predicate=ONTO.Peso)
        graph.add((nomSuj, RDF.type, ONTO.Producto))
        graph.add((nomSuj, ONTO.Nombre, nombreProd))
        graph.add((nomSuj, ONTO.Peso, peso))
        # Añadimos el producto en la relacion ProductosCompra.
        graph.add((compra, ONTO.ProductosCompra, URIRef(nomSuj)))
    # Añadimos el nombre del centro logístico.
    graph.add((compra, ONTO.NombreCL, Literal(centro, datatype=XSD.string)))
    # Enviamos los datos de la compra para que el centro logístico pueda enviarla.
    graph.add((accion, ONTO.Envia, URIRef(compra)))
    msg = build_message(graph, ACL.request, AgGestorCompra.uri, AgCentroLogistico.uri, accion, count)
    gr = send_message(msg, AgCentroLogistico.address)

    global precio_total_compra
    precio_total_compra = preutotal
    PedidosFile = open('../Data/RegistroPedidos')
    graphfinal = Graph()
    graphfinal.parse(PedidosFile, format='turtle')
    grafrespuesta=Graph()
    grafrespuesta.add((compra, RDF.type, ONTO.Compra))
    grafrespuesta.add((compra, ONTO.PrecioTotal, Literal(preutotal, datatype=XSD.float)))
    grafrespuesta.add((compra, ONTO.TarjetaCredito, Literal(tarjeta, datatype=XSD.string)))
    grafrespuesta.add((compra, ONTO.Ciudad, Literal(city, datatype=XSD.string)))
    grafrespuesta.add((compra,ONTO.DNI,Literal(dni)))
    productos = gm.objects(content, ONTO.ProductosPedido)
    for producto in productos:
        nombreProd = gm.value(subject=producto, predicate=ONTO.Nombre)
        nomSuj = gm.value(predicate=ONTO.Nombre, object=nombreProd)
        # Añadimos el producto en la relacion ProductosCompra.
        grafrespuesta.add((compra, ONTO.ProductosCompra, Literal(nombreProd,datatype=XSD.string)))

    for s, p, o in gr:
        if p == ONTO.FechaEntrega:
            grafrespuesta.add((compra,ONTO.FechaEntrega,Literal(o,datatype=XSD.string)))
        elif p == ONTO.NombreTransportista:
            grafrespuesta.add((compra,ONTO.NombreTransportista,Literal(o,datatype=XSD.string)))
        elif p == ONTO.Lote:
            grafrespuesta.add((compra,ONTO.Lote,s)) # TODO pot estar malament
    graphfinal += grafrespuesta
    # Añadimos la nueva compra y lo escribimos otra vez.
    PedidosFile = open('../Data/RegistroPedidos', 'wb')
    PedidosFile.write(graphfinal.serialize(format='turtle'))
    PedidosFile.close()
    grafrespuesta.add((accion, RDF.type, ONTO.ProcesarEnvio))
    print("rebut gc :)")
    for s, p, o in grafrespuesta:
        print(s)
        print(p)
        print(o)
    msg = build_message(grafrespuesta, ACL.request, AgGestorCompra.uri, AgAsistente.uri, accion, count)
    send_message(msg, AgAsistente.address)


def agentbehavior1(cola):
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
