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

from Agentes import AgCentroLogistico
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
                          agn.AgCentroLogisticoBCN,
                          'http://%s:9014/comm' % hostname,
                          'http://%s:9014/Stop' % hostname)
AgCentroLogisticoNY = Agent('AgCentroLogisticoBCN',
                            agn.AgAsistente,
                            'http://%s:9015/comm' % hostname,
                            'http://%s:9015/Stop' % hostname)
AgCentroLogisticoPK = Agent('AgCentroLogisticoBCN',
                            agn.AgAsistente,
                            'http://%s:9016/comm' % hostname,
                            'http://%s:9016/Stop' % hostname)

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
                numero_productos = 0
                precio_total = 0.0
                graffactura = Graph()  # city, priority, targ credit, urirefs productes
                count_real = get_count()
                count = str(count_real)
                factura = ONTO["Factura_" + count]
                accion = ONTO["EnviarFactura_" + count]

                graffactura.add((accion, RDF.type, ONTO.EnviarFactura))
                graffactura.add((accion, ONTO.FacturaEnviada, URIRef(factura)))
                graffactura.add((factura, RDF.type, ONTO.Factura))

                ciudad = gm.objects(content, ONTO.Ciudad)
                for c in ciudad:
                    city = gm.value(subject=c, predicate=ONTO.Ciudad)
                    graffactura.add((c, RDF.type, ONTO.Ciudad))
                    graffactura.add((c, ONTO.Ciudad, city))
                    graffactura.add((factura, ONTO.Ciudad, Literal(city)))
                    break

                prioridad = gm.objects(content, ONTO.PrioridadEntrega)
                for p in prioridad:
                    priority = gm.value(subject=p, predicate=ONTO.PrioridadEntrega)
                    graffactura.add((p, RDF.type, ONTO.PrioridadEntrega))
                    graffactura.add((p, ONTO.PrioridadEntrega, priority))
                    graffactura.add((factura, ONTO.PrioridadEntrega, Literal(priority)))
                    break

                tarjcred = gm.objects(content, ONTO.TarjetaCredito)
                for t in tarjcred:
                    creditCard = gm.value(subject=t, predicate=ONTO.TarjetaCredito)
                    graffactura.add((t, RDF.type, ONTO.TarjetaCredito))
                    graffactura.add((t, ONTO.TarjetaCredito, creditCard))
                    graffactura.add((factura, ONTO.TarjetaCredito, Literal(creditCard)))
                    break

                productos = gm.objects(content, ONTO.ProductosPedido)
                for producto in productos:
                    numero_productos += 1
                    precio_total += float(gm.value(subject=producto, predicate=ONTO.PrecioProducto))
                    nombreProd = gm.value(subject=producto, predicate=ONTO.Nombre)
                    nomSuj = gm.value(predicate=ONTO.Nombre, object=nombreProd)
                    graffactura.add((nomSuj, RDF.type, ONTO.Nombre))
                    graffactura.add((nomSuj, ONTO.Nombre, nombreProd))
                    graffactura.add((factura, ONTO.ProductosFactura, nomSuj))

                graffactura.add((factura, ONTO.NumeroProductos, Literal(numero_productos)))
                priceOnto = ONTO['PrecioTotal_' + str(count)]
                graffactura.add((priceOnto, RDF.type, ONTO.PrecioTotal))
                graffactura.add((priceOnto, ONTO.PrecioTotal, Literal(precio_total)))
                graffactura.add((factura, ONTO.PrecioTotal, Literal(precio_total)))

                # msg = build_message(graffactura, ACL.response, AgGestorCompra.uri, AgAsistente.uri, accion, count_real)
                # print(msg.serialize(format='xml'))
                # print(requests.get(AgAsistente.uri, params={'content': msg}).text)
                # send_message(msg, AgAsistente.address)
                empezar_proceso = Process(target=procesar_compra, args=(
                    count_real, graffactura, gm, precio_total, content, priority, creditCard))
                empezar_proceso.start()
                return graffactura.serialize(format='xml'), 200


def procesar_compra(count=0.0, factura=Graph(), gm=Graph(), preutotal=0.0, content="", prioridad=0, tarjeta=""):
    logger.info("Procesando compra...")
    ciudad = gm.objects(content, ONTO.Ciudad)
    accion = ONTO["EnviarPaquete_" + str(count)]
    centro = ""
    city = ""
    for c in ciudad:
        city = gm.value(subject=c, predicate=ONTO.Ciudad)
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
    graph = Graph()
    PedidosFile = open('../Data/PedidosEnCurso')
    graph.parse(PedidosFile, format='xml')
    graphfinal = Graph()
    PedidosFile = open('../Data/PedidosFinalizados')
    graphfinal.parse(PedidosFile, format='xml')
    identificador = "Compra_" + str(random.randint(1000, 25000)) + str(random.randint(1000, 25000))
    uri = "http://www.owl-ontologies.com/OntologiaECSDI.owl#" + identificador
    subject = URIRef(uri)
    graph.add((subject, RDF.type, ONTO.Compra))
    graph.add((subject, ONTO.Ciudad, Literal(city, datatype=XSD.string)))
    graph.add((subject, ONTO.Identificador, Literal(identificador, datatype=XSD.string)))
    graph.add((subject, ONTO.PrecioTotal, Literal(preutotal, datatype=XSD.float)))
    graph.add((subject, ONTO.PrioridadEntrega, Literal(prioridad, datatype=XSD.float)))
    graph.add((subject, ONTO.TarjetaCredito, Literal(tarjeta, datatype=XSD.string)))
    productos = gm.objects(content, ONTO.ProductosPedido)
    for producto in productos:
        nombreProd = gm.value(subject=producto, predicate=ONTO.Nombre)
        nomSuj = gm.value(predicate=ONTO.Nombre, object=nombreProd)
        peso = gm.value(subject=producto, predicate=ONTO.Peso)
        graph.add((nomSuj, RDF.type, ONTO.Contiene))
        graph.add((nomSuj, ONTO.Nombre, nombreProd))
        graph.add((nomSuj, ONTO.Peso, peso))
        graph.add((subject, ONTO.ProductosFactura, URIRef(nomSuj)))
    graph.add((subject, ONTO.NombreCL, centro))
    PedidosFile = open('../Data/PedidosEnCurso', 'wb')
    PedidosFile.write(graph.serialize(format='xml'))
    PedidosFile.close()
    logger.info("La compra_" + str(count) + " se ha registrado en la base de datos.")
    msg = build_message(graph, ACL.request, AgGestorCompra.uri, AgCentroLogistico.uri, accion, count)
    gr = send_message(msg, AgCentroLogistico.address)
    graphfinal += graph
    informacion_entrega = {}
    for s, p, o in gr:
        if p == ONTO.PrecioTransporte:
            informacion_entrega["PrecioTransporte"] = o
        elif p == ONTO.Fecha:
            informacion_entrega["Fecha"] = o
        elif p == ONTO.Nombre:
            informacion_entrega["Nombre"] = o
    logger.info("El transportista "+ str(informacion_entrega["nombre"])+ " se entregará la compra en la fecha: "+ informacion_entrega["Fecha"])
    graphfinal.add((subject, ONTO.Fecha, informacion_entrega["Fecha"]))
    graphfinal.add((subject, ONTO.Nombre, informacion_entrega["Nombre"]))

    PedidosHechos = open('../Data/PedidosFinalizados', 'wb')
    PedidosHechos.write(graphfinal.serialize(format='xml'))
    PedidosFile.close()
    logger.info("La compra ya se ha enviado y ha quedado registrada en la base de datos.")
    return
    """
    compra = Graph()
    id = ONTO["ProcesarCompra_" + str(count)]
    msgdic = get_message_properties(gm)
    content = msgdic['content']
    productos = gm.objects(content, ONTO.Producto)
    date = ONTO[datetime.today().strftime('%Y-%m-%d')]
    compra.add(id, RDF.type, ONTO.Compra)
    compra.add(id, ONTO.PrioridadEntrega, gm.objects(content, ONTO.PrioridadEntrega))
    compra.add(id, ONTO.Ciudad, gm.objects(content, ONTO.Ciudad))
    compra.add(id, ONTO.TarjetaCredito, gm.objects(content, ONTO.TarjetaCredito))
    compra.add(id, ONTO.Fecha, date)
    compra.add(id, ONTO.Factura, URIRef(factura))
    for prod in productos:
        compra.add(id, ONTO.ProductosCompra, URIRef(prod))
    accion = ONTO["Procesar_compra" + str(count)]
    g.add((accion, RDF.type, ONTO.ProcesarCompra))
    msg = build_message(compra, ACL.request, AgGestorCompra.uri, AgProcesadorPedidos.uri, accion, count)
    send_message(msg, AgProcesadorPedidos.address)
    """


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
