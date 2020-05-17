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

from rdflib import URIRef,Namespace, Graph, FOAF
from flask import Flask, request
import rdflib

from AgentUtil.FlaskServer import shutdown_server
from AgentUtil.Agent import Agent
__author__ = 'pau-laia-anna'

"""
# Configuration stuff
hostname = socket.gethostname()
port = 9011

agn = Namespace("http://www.agentes.org#")

# Contador de mensajes
mss_cnt = 0

# Datos del Agente

AgProva = Agent('AgProva',
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

resultats = []
# Flask stuff

app = Flask(__name__)

@app.route("/sum")
def suma():
    num1 = request.args['numero1']
    num2 = request.args['numero2']
    resultats.append(int(num1)+int(num2))
    return str(int(num1)+int(num2))

@app.route("/comm")
def comunicacion():
    
    Entrypoint de comunicacion
    
    global dsgraph
    global mss_cnt
    return str(resultats)


@app.route("/Stop")
def stop():
    
    Entrypoint que para el agente

    :return:
    
    tidyup()
    shutdown_server()
    return "Parando Servidor"


def tidyup():
    
    Acciones previas a parar el agente

    
    pass


def agentbehavior1(cola):
    
    Un comportamiento del agente

    :return:
    
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
"""
g = Graph()
 
g.parse('C:/Users/pauca/Desktop/ECSDI/Ontologia.owl', format='xml')
name = Namespace('C:/Users/pauca/Desktop/ECSDI/Ontologia.owl')
#print(g.triples(None,FOAF.name,"hasdh"))
"""
for s, p, o in g:
    if (str(s) == "http://www.semanticweb.org/pauca/ontologies/2020/3/untitled-ontology-4#Producto_5PLUYF"):
        print(str(p) + " : " +str(o))
    #print("Sujeto " + str(s))
    #print("Predicado " + str(p))
    #print("Objeto " + str(o))
"""
node = URIRef('http://mundo.mundial.org/persona/pedro')

res = g.query(""" PREFIX foaf: <http://xmlns.com/foaf/0.1/>
                    SELECT DISTINCT ?a ?Nombre
                    WHERE {
                        ?a foaf:age ?PrecioProducto .
                        ?a foaf:name ?Nombre .
                        FILTER {?PrecioProducto > 18}
                        }""")
