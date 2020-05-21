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

__author__ = 'pau-laia-anna'
logger = config_logger(level=1)

# Configuration stuff
hostname = socket.gethostname()
port = 9013

agn = Namespace("http://www.agentes.org#")

# Contador de mensajes
mss_cnt = 0

# Datos del Agente

AgProcesadorPedidos = Agent('AgProcesadorPedidos',
                       agn.AgProcesadorPedidos,
                       'http://%s:%d/comm' % (hostname, port),
                       'http://%s:%d/Stop' % (hostname, port))

AgGestorCompra = Agent('AgGestorCompra',
                       agn.AgGestorCompra,
                       'http://%s:9012/comm' % (hostname, port),
                       'http://%s:9012/Stop' % (hostname, port))

# Directory agent address
DirectoryAgent = Agent('DirectoryAgent',
                       agn.Directory,
                       'http://%s:9000/Register' % hostname,
                       'http://%s:9000/Stop' % hostname)



# Global triplestore graph
dsgraph = Graph()

cola1 = Queue()

# Flask stuff
app = Flask(__name__)

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
