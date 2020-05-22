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

import time, random
import argparse
import socket
import sys
import requests
from multiprocessing import Queue, Process
from flask import Flask, request
from pyparsing import Literal
from rdflib import URIRef, XSD, Namespace, Graph
from Util.ACLMessages import *
from Util.Agent import Agent
from Util.FlaskServer import shutdown_server
from Util.Logging import config_logger
from Util.OntoNamespaces import ONTO
from datetime import datetime

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
                    'http://%s:9011/Register' % hostname,
                    'http://%s:9011/Stop' % hostname)
AgProcesadorPedidos = Agent('AgAsistente',
                            agn.AgAsistente,
                            'http://%s:9013/Register' % hostname,
                            'http://%s:9013/Stop' % hostname)

# Global triplestore graph
dsgraph = Graph()

cola1 = Queue()

# Flask stuff
app = Flask(__name__)


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
                graffactura = Graph()  #city, priority, targ credit, urirefs productes
                count = str(get_count())
                factura = ONTO["Factura_" + count]
                accion = ONTO["EnviarFactura_" + count]
                graffactura.add((accion, RDF.type, ONTO.EnviarFactura))
                graffactura.add((factura, RDF.type, ONTO.Factura))
                graffactura.add((accion, ONTO.FacturaEnviada, URIRef(factura)))
                ciudad = gm.objects(content, ONTO.Ciudad)
                for c in ciudad:
                    city = gm.value(subject=c, predicate=ONTO.Ciudad)
                    graffactura.add((c, RDF.type, ONTO.Ciudad))
                    graffactura.add((factura, ONTO.Ciudad, Literal(city)))

                prioridad = gm.objects(content, ONTO.Prioridad)
                for p in prioridad:
                    priority = gm.value(subject=p, predicate=ONTO.Prioridad)
                    graffactura.add((factura, ONTO.Prioridad, Literal(priority)))

                tarjcred = gm.objects(content, ONTO.TarjetaCredito)
                for t in tarjcred:
                    creditCard = gm.value(subject=t, predicate=ONTO.TarjetaCredito)
                    graffactura.add((factura, ONTO.TarjetaCredito, Literal(creditCard)))

                productos = gm.objects(content, ONTO.ProductosPedido)
                for producto in productos:
                    prod = gm.value(subject=producto, predicate=ONTO.Producto)
                    print(prod)
                    graffactura.add((factura, ONTO.ProductosCompra, URIRef(producto)))
                    numero_productos += 1
                    print("sujeto " + producto)
                    print("OBJ " + str(gm.value(subject=producto, predicate=ONTO.PrecioProducto)))
                    precio_total += float(str(gm.value(subject=producto, predicate=ONTO.PrecioProducto)))
                graffactura.add((factura, ONTO.NumeroProductos, Literal(numero_productos)))
                graffactura.add((factura, ONTO.PrecioTotal, Literal(precio_total)))
                msg = build_message(graffactura, ACL.response, AgGestorCompra.uri, AgAsistente.uri, accion, count)
                send_message(msg, AgAsistente.address)
                procesar_compra(count, gm, precio_total, graffactura)


def procesar_compra(count=0, gm=Graph(), factura=Graph()):
    logger.info("Procesando compra...")
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