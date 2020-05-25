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
from rdflib import URIRef, XSD, Namespace, Graph, Literal

from Agentes import AgTransportista
from Util.ACLMessages import *
from Util.Agent import Agent
from Util.FlaskServer import shutdown_server
from Util.Logging import config_logger
from Util.OntoNamespaces import ONTO

__author__ = 'pau-laia-anna'
logger = config_logger(level=1)

# Configuration stuff
hostname = socket.gethostname()
port = 9014

agn = Namespace("http://www.agentes.org#")

# Contador de mensajes
mss_cnt = 0

# Datos del Agente

AgCentroLogistico = Agent('AgCentroLogistico',
                          agn.AgCentroLogisticoBCN,
                          'http://%s:%d/comm' % (hostname, port),
                          'http://%s:%d/Stop' % (hostname, port))

AgGestorCompra = Agent('AgGestorCompra',
                       agn.AgGestorCompra,
                       'http://%s:9012/comm' % (hostname),
                       'http://%s:9012/Stop' % (hostname))

# Directory agent address
DirectoryAgent = Agent('DirectoryAgent',
                       agn.Directory,
                       'http://%s:9000/Register' % hostname,
                       'http://%s:9000/Stop' % hostname)
AgTransportista = Agent('AgTransportista',
                        agn.Transportista,
                        'http://%s:9015/comm' % hostname,
                        'http://%s:9015/Stop' % hostname)

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
    global centro
    message = request.args['content']
    gm = Graph()
    gm.parse(data=message)

    msgdic = get_message_properties(gm)

    gr = None
    if msgdic is None:
        # Si no es, respondemos que no hemos entendido el mensaje
        gr = build_message(Graph(), ACL['not-understood'], sender=AgCentroLogistico.uri, msgcnt=get_count())
    else:
        # Obtenemos la performativa
        if msgdic['performative'] != ACL.request:
            # Si no es un request, respondemos que no hemos entendido el mensaje
            gr = build_message(Graph(),
                               ACL['not-understood'],
                               sender=AgCentroLogistico.uri,
                               msgcnt=get_count())
        else:
            # Extraemos el objeto del contenido que ha de ser una accion de la ontologia
            # de registro
            content = msgdic['content']
            # Averiguamos el tipo de la accion
            accion = gm.value(subject=content, predicate=RDF.type)

            # Accion de busqueda
            if accion == ONTO.EnviarPaquete:
                productos = gm.objects(content, ONTO.Contiene)
                graph = Graph()
                count = get_count()
                identificador = "Lote_" + str(count)
                subject = "http://www.owl-ontologies.com/OntologiaECSDI.owl#" + identificador
                graph.add((subject, RDF.type, ONTO.Lote))
                graph.add((subject, ONTO.Identificador, Literal(identificador, datatype=XSD.string)))
                ciudad = gm.objects(content, ONTO.Ciudad)
                for c in ciudad:
                    city = gm.value(subject=c, predicate=ONTO.Ciudad)
                    graph.add((subject, ONTO.Ciudad, Literal(city)))
                    break
                prioridad = gm.objects(content, ONTO.PrioridadEntrega)
                for p in prioridad:
                    priority = gm.value(subject=p, predicate=ONTO.PrioridadEntrega)
                    graph.add((subject, ONTO.PrioridadEntrega, Literal(priority)))
                    break
                cl = gm.objects(content, ONTO.NombreCL)
                for clog in cl:
                    centro = gm.value(subject=clog, predicate=ONTO.NombreCL)
                peso_total = 0
                for producto in productos:
                    nombreProd = gm.value(subject=producto, predicate=ONTO.Nombre)
                    peso_total += gm.value(subject=producto, predicate=ONTO.Peso)
                    # nomSuj = gm.value(predicate=ONTO.Nombre, object=nombreProd)
                    # graph.add((nomSuj, RDF.type, ONTO.Producto))
                    # graph.add((nomSuj, ONTO.Nombre, nombreProd))
                    # graph.add((subject, ONTO.Contiene, URIRef(nomSuj)))
                graph.add((subject, ONTO.Peso, peso_total))
                graph.add((subject, ONTO.NombreCL, centro))
                gr = send_message(
                    build_message(gm, ACL.request, AgCentroLogistico.uri, AgTransportista.uri, accion, count), AgTransportista.address)
                info = {}
                for s, p, o in gr:
                    if p == ONTO.PrecioTransporte:
                        info["PrecioTransporte"] = o
                    elif p == ONTO.Fecha:
                        info["Fecha"] = o
                gr = Graph()
                accion = ONTO["ConfirmarTransportista_" + str(count)]
                grr = send_message(
                    build_message(gr, ACL.request, AgCentroLogistico.uri, AgTransportista.uri, accion, count), AgTransportista.address)
                return gr.serialize(format="xml"), 200


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