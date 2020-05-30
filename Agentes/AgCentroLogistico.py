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
            if accion == ONTO.ProcesarEnvio:
                #Se genera un grafo con la informacion necesaria para negociar el envío.
                count = get_count()
                action= ONTO["PedirPreciosEnvio_"+ str(count)]
                lote = ONTO["Lote_"+str(count)]
                graph = Graph()
                peso_total = 0
                graph.add((action, RDF.type, ONTO.PedirPreciosEnvio))
                # TODO un lote no equival a una compra, son diverses compres amb igual ciutat i prioritat (per exemple)
                graph.add((lote,RDF.type,ONTO.Lote))
                for s,p,o in gm:
                    if p == ONTO.Ciudad:
                        graph.add((lote, ONTO.Ciudad, Literal(o,datatype=XSD.string)))
                    elif p == ONTO.PrioridadEntrega:
                        graph.add((lote, ONTO.PrioridadEntrega, Literal(o,datatype=XSD.float)))
                    elif p == ONTO.NombreCL:
                        graph.add((action, ONTO.NombreCL,Literal(o,datatype=XSD.string)))
                    elif p ==ONTO.Peso:
                        peso_total+=float(o)
                    elif p == ONTO.Nombre:
                        graph.add((s, RDF.type, ONTO.Producto))
                        graph.add((s, ONTO.Nombre, Literal(o,datatype=XSD.string)))
                        graph.add((lote, ONTO.Contiene, URIRef(s)))
                graph.add((lote,ONTO.Peso,Literal(peso_total,datatype=XSD.float)))
                #La accion es pedir precios envio, y conteine un lote como informacion.
                graph.add((action, ONTO.Lote,URIRef(lote)))
                """
                #A partir de aqui se añaden los atributos del lote.
                graph.add((lote,ONTO.Identificador,Literal(lote,datatype=XSD.string)))
                ciudad = gm.objects(item, ONTO.Ciudad)
                for c in ciudad:
                    city = gm.value(subject=c, predicate=ONTO.Ciudad)
                    graph.add((lote, ONTO.Ciudad, Literal(city)))
                    print(city)
                    break
                prioridad = gm.objects(item, ONTO.PrioridadEntrega)
                for p in prioridad:
                    priority = gm.value(subject=p, predicate=ONTO.PrioridadEntrega)
                    graph.add((lote, ONTO.PrioridadEntrega, Literal(priority)))
                    print(priority)
                    break
                cl = gm.objects(item, ONTO.NombreCL)
                for clog in cl:
                    centro = gm.value(subject=clog, predicate=ONTO.NombreCL)
                    graph.add((action, ONTO.NombreCL, Literal(centro,datatype=XSD.string)))
                    print(centro)
                    break
                    peso_total = 0
                    productos = gm.objects(item, ONTO.ProductosCompra)
                    for producto in productos:
                        #A parte del peso, añadimos los nombres simulando que lo necesitan los transportistas.
                        nombreProd = gm.value(subject=producto, predicate=ONTO.Nombre)
                        peso_total += gm.value(subject=producto, predicate=ONTO.Peso)
                        nomSuj = gm.value(predicate=ONTO.Nombre, object=nombreProd)
                        graph.add((nomSuj, RDF.type, ONTO.Producto))
                        graph.add((nomSuj, ONTO.Nombre, Literal(nombreProd,datatype=XSD.string)))
                        graph.add((lote, ONTO.Contiene, URIRef(nomSuj)))
                    graph.add((action, ONTO.Peso, Literal(peso_total, datatype=XSD.float)))
                    """
                # TODO FIPA-CONTRACT NEt
                gr = send_message(
                    build_message(graph, ACL.request, AgCentroLogistico.uri, AgTransportista.uri, action, count), AgTransportista.address)
                info = {}
                for s, p, o in gr:
                    if p == ONTO.PrecioTransporte:
                        info["PrecioTransporte"] = o
                    elif p == ONTO.Fecha:
                        info["Fecha"] = o
                    elif p == ONTO.Nombre:
                        info["NombreTransportista"] = o
                compra = ONTO["Compra_" + str(count)]
                gm.add((compra,ONTO.FechaEntrega,Literal(info["Fecha"],datatype=XSD.string)))
                transportista = ONTO[info["NombreTransportista"]]
                gm.add((transportista,RDF.type,ONTO.Transportista))
                gm.add((transportista,ONTO.NombreTransportista,Literal(info["NombreTransportista"],datatype=XSD.string)))
                gm.add((compra,ONTO.EntregadaPor,URIRef(transportista)))
                gm.add((compra,ONTO.FechaEntrega,Literal(info["Fecha"],datatype=XSD.string)))
                grafo_confirmacion = Graph()
                accion = ONTO["EnviarPaquete_" + str(count)]
                grafo_confirmacion.add((accion, RDF.type, ONTO.EnviarPaquete))
                grr = send_message(
                    build_message(grafo_confirmacion, ACL.request, AgCentroLogistico.uri, AgTransportista.uri, accion, count), AgTransportista.address)
                return gm.serialize(format="xml"), 200
            else:
                # TODO respuesta pedirpreciosenvio y predir contraofertas
                resposta= Graph()
                return resposta.serialize(format="xml"),200


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