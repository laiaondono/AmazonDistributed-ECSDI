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
port = 9016

agn = Namespace("http://www.agentes.org#")

# Contador de mensajes
mss_cnt = 0
# Datos del Agente

AgEmpresaExterna = Agent('AgEmpresaExterna',
                       agn.AgEmpresaExterna,
                       'http://%s:%d/comm' % (hostname, port),
                       'http://%s:%d/Stop' % (hostname, port))


# Directory agent address
AgGestorProductos = Agent('AgGestorProductos',
                    agn.AgGestorProductos,
                    'http://%s:9017/comm' % hostname,
                    'http://%s:9017/Stop' % hostname)


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
        gr = build_message(Graph(), ACL['not-understood'], sender=AgEmpresaExterna.uri, msgcnt=get_count())
    else:
        # Obtenemos la performativa
        if msgdic['performative'] != ACL.request:
            # Si no es un request, respondemos que no hemos entendido el mensaje
            gr = build_message(Graph(),
                               ACL['not-understood'],
                               sender=AgEmpresaExterna.uri,
                               msgcnt=get_count())
        else:
            # Extraemos el objeto del contenido que ha de ser una accion de la ontologia
            # de registro
            content = msgdic['content']
            # Averiguamos el tipo de la accion
            accion = gm.value(subject=content, predicate=RDF.type)

            # Accion de busqueda
           # if accion == ONTO.HacerPedido:

@app.route("/")
def inicio():
    return "Utiliza el path /añadir_producto para añadir un producto externo"

@app.route("/añadir_producto")
def añadir():
    return "Aqui se podra rellenar un formulario para añadir el producto externo."