# -*- coding: utf-8 -*-
"""
Agente Buscador de productos.
Esqueleto de agente usando los servicios web de Flask

/comm es la entrada para la recepcion de mensajes del agente
/Stop es la entrada que para el agente

Tiene una funcion AgentBehavior1 que se lanza como un thread concurrente

Asume que el agente de registro esta en el puerto 9000

@author: javier
"""

from multiprocessing import Process, Queue
import socket
import time, random
from rdflib import Namespace, Graph
from flask import Flask, request
import requests

from AgentUtil.FlaskServer import shutdown_server
from AgentUtil.Agent import Agent

__author__ = 'pau-laia-anna'


# Configuration stuff
hostname = socket.gethostname()
port = 9010

agn = Namespace("http://www.agentes.org#")

# Contador de mensajes
mss_cnt = 0

# Datos del Agente

AgBuscadorProductos = Agent('BuscadorProductos',
                       agn.AgenteSimple,
                       'http://%s:%d/comm' % (hostname, port),
                       'http://%s:%d/Stop' % (hostname, port))

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


def test_suma():
    peticion = {"numero1": random.randint(0,400), "numero2": random.randint(0,400)}
    port_agprova = 9011
    uri = 'http://desktop-lrtmd2a:9011/sum'
    print(uri)
    print(peticion)
    headers = {'content-type': 'application/json'}
    r= requests.get(uri,params=peticion, headers = headers)
    print(r.text)
    return r.text


def busca():
    peticion = {"numero1": random.randint(0,400), "numero2": random.randint(0,400)}
    port_agprova = 9011
    uri = 'http://desktop-lrtmd2a:9011/sum'
    print(uri)
    print(peticion)
    headers = {'content-type': 'application/json'}
    r= requests.get(uri,params=peticion, headers = headers)
    print(r.text)
    return r.text


@app.route("/comm")
def comunicacion():
    """
    Entrypoint de comunicacion
    """
    resposta = test_suma()
    return str(resposta)
  
@app.route("/search")
def busca():
    """
    Entrypoint de comunicacion
    """
    resposta = busca()
    return str(resposta)  
    


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


