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
port = 9017

agn = Namespace("http://www.agentes.org#")

# Contador de mensajes
mss_cnt = 6

# Datos del Agente
AgVendedorExterno = Agent('AgVendedorExterno',
                          agn.AgVendedorExterno,
                          'http://%s:9018/comm' % hostname,
                          'http://%s:9018/Stop' % hostname)

AgGestorProductos = Agent('AgGestorProductos',
                          agn.AgGestorProductos,
                          'http://%s:%d/comm' % (hostname, port),
                          'http://%s:%d/Stop' % (hostname, port))


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
        gr = build_message(Graph(), ACL['not-understood'], sender=AgGestorProductos.uri, msgcnt=get_count())
    else:
        # Obtenemos la performativa
        if msgdic['performative'] != ACL.request:
            # Si no es un request, respondemos que no hemos entendido el mensaje
            gr = build_message(Graph(),
                               ACL['not-understood'],
                               sender=AgGestorProductos.uri,
                               msgcnt=get_count())
        else:
            # Extraemos el objeto del contenido que ha de ser una accion de la ontologia
            # de registro
            content = msgdic['content']
            # Averiguamos el tipo de la accion
            accion = gm.value(subject=content, predicate=RDF.type)

            if accion == ONTO.AñadirProductoExterno:
                ProdExtFile = open('C:/Users/pauca/Documents/GitHub/ECSDI_Practica/Data/ProductosExternos')
                graphfinal = Graph()
                graphfinal.parse(ProdExtFile, format='xml')

                graphNewProduct = Graph()
                # Nombre, Marca, Empresa, CantidadValoraciones, Valoracion, Peso, Categoria, PrecioProducto, Identificador
                nombre = 1
                for s, p, o in graphfinal:
                    if p == ONTO.Identificador:
                        nombre+=1

                identificador = 'ProductoEX_' + str(nombre)
                print("ID: " + identificador)
                productSuj = ONTO[identificador]
                print(productSuj)
                graphNewProduct.add((productSuj, RDF.type, ONTO.Producto))
                graphNewProduct.add((productSuj, ONTO.Identificador, Literal(identificador)))
                for s, p, o in gm:
                    if p == ONTO.Nombre:
                        graphNewProduct.add((productSuj, ONTO.Nombre, Literal(o)))
                    elif p == ONTO.NombreEmpresa:
                        graphNewProduct.add((productSuj, ONTO.Empresa, Literal(o)))
                    if p == ONTO.Marca:
                        graphNewProduct.add((productSuj, ONTO.Marca, Literal(o)))
                    if p == ONTO.PrecioProducto:
                        graphNewProduct.add((productSuj, ONTO.PrecioProducto, Literal(o)))
                    if p == ONTO.Peso:
                        graphNewProduct.add((productSuj, ONTO.Peso, Literal(o)))
                    if p == ONTO.Categoria:
                        graphNewProduct.add((productSuj, ONTO.Categoria, Literal(o)))

                graphNewProduct.add((productSuj, ONTO.Valoracion, Literal(5)))
                graphNewProduct.add((productSuj, ONTO.CantidadValoraciones, Literal(1)))

                # Añadimos el nuevo producto externo y lo escribimos otra vez.
                graphfinal += graphNewProduct
                PedidosFile = open('C:/Users/pauca/Documents/GitHub/ECSDI_Practica/Data/ProductosExternos', 'wb')
                PedidosFile.write(graphfinal.serialize(format='xml'))
                PedidosFile.close()

                g = Graph()
                return g.serialize(format='xml'), 200


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