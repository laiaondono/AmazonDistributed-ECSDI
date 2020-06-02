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

port = 9013

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
AgProcesadorOpiniones = Agent('AgProcesadorOpiniones',
                    agn.AgProcesadorOpiniones,
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

AgAsistente = Agent('AgAsistente',
                       agn.AgAsistente,
                       'http://%s:9011/Register' % hostname,
                       'http://%s:9011/Stop' % hostname)


# Global triplestore graph
dsgraph = Graph()

cola1 = Queue()

resultats = []

# Flask stuff
app = Flask(__name__, template_folder='../templates')

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
        gr = build_message(Graph(), ACL['not-understood'], sender=AgProcesadorOpiniones.uri, msgcnt=str(mss_cnt))
    else:
        # Obtenemos la performativa
        if msgdic['performative'] != ACL.request:
            # Si no es un request, respondemos que no hemos entendido el mensaje
            gr = build_message(Graph(),
                               ACL['not-understood'],
                               sender=AgProcesadorOpiniones.uri,
                               msgcnt=str(mss_cnt))
        else:
            # Extraemos el objeto del contenido que ha de ser una accion de la ontologia
            # de registro
            content = msgdic['content']
            # Averiguamos el tipo de la accion
            accion = gm.value(subject=content, predicate=RDF.type)

            # Accion de busqueda
            if accion == ONTO.ActualizarHistorial:
                gr =Graph()
                PedidosFile = open('../Data/Historial')
                graphfinal = Graph()
                graphfinal.parse(PedidosFile, format='turtle')
                #for s, p, o in graphfinal:
                #    if p == ONTO.Producto
                count = 0
                graph_adicionals = Graph()
                dni =""
                for s,p,o in gm:
                    count+=1
                    historial = ONTO["Historial_" + str(count)]
                    graph_adicionals.add((historial,RDF.type,ONTO.Historial))
                    if (p == ONTO.DNI):
                        dni = str(o)

                for s,p,o in gm:
                    count+=1
                    historial = ONTO["Historial_" + str(count)]
                    graph_adicionals.add((historial,RDF.type,ONTO.Historial))
                    if p ==ONTO.Identificador:
                        graph_adicionals.add((historial,ONTO.Identificador,Literal(str(o))))
                        graph_adicionals.add((historial,ONTO.DNI,Literal(str(dni))))
                graphfinal+=graph_adicionals
                PedidosFile = open('../Data/Historial', 'wb')
                PedidosFile.write(graphfinal.serialize(format='turtle'))
                PedidosFile.close()
                return gr.serialize(format="xml"),200



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




