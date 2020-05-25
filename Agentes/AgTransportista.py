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
from Util.ACLMessages import *
from Util.Agent import Agent
from Util.FlaskServer import shutdown_server
from Util.Logging import config_logger
from Util.OntoNamespaces import ONTO
from opencage.geocoder import OpenCageGeocode
from geopy.geocoders import Nominatim
from geopy.distance import geodesic, great_circle
from geopy import geocoders
from datetime import datetime
import time
__author__ = 'pau-laia-anna'
logger = config_logger(level=1)

# Configuration stuff
hostname = socket.gethostname()
port = 9015

agn = Namespace("http://www.agentes.org#")

# Contador de mensajes
mss_cnt = 0

# Datos del Agente

AgTransportista = Agent('AgTransportista',
                          agn.AgTransportista,
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

AgCentroLogistico =Agent('AgCentroLogistico',
                        agn.Directory,
                        'http://%s:9014/comm' % hostname,
                        'http://%s:9014/Stop' % hostname)


location_ny = ( Nominatim(user_agent='myapplication').geocode("New York").latitude, Nominatim(user_agent='myapplication').geocode("New York").longitude)
location_bcn = (Nominatim(user_agent='myapplication').geocode("Barcelona").latitude,Nominatim(user_agent='myapplication').geocode("Barcelona").longitude)
location_pk = (Nominatim(user_agent='myapplication').geocode("Pekín").latitude,Nominatim(user_agent='myapplication').geocode("Pekín").longitude)

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
        gr = build_message(Graph(), ACL['not-understood'], sender=AgTransportista.uri, msgcnt=get_count())
    else:
        # Obtenemos la performativa
        if msgdic['performative'] != ACL.request:
            # Si no es un request, respondemos que no hemos entendido el mensaje
            gr = build_message(Graph(),
                               ACL['not-understood'],
                               sender=AgTransportista.uri,
                               msgcnt=get_count())
        else:
            content = msgdic['content']
            # Averiguamos el tipo de la accion
            accion = gm.value(subject=content, predicate=RDF.type)
            peso_total=0
            if accion == ONTO.ConsensuarTransportista:
                peso = gm.objects(content,ONTO.Peso)
                for p in peso:
                    peso_total = gm.value(subject=p,predicate=ONTO.Peso)
                    break
                ciudad = gm.objects(content, ONTO.Ciudad)
                for c in ciudad:
                    city = gm.value(subject=c, predicate=ONTO.Ciudad)
                prioridad = gm.objects(content, ONTO.PrioridadEntrega)
                for p in prioridad:
                    priority = gm.value(subject=p, predicate=ONTO.PrioridadEntrega)
                cl = gm.objects(content, ONTO.NombreCL)
                for clog in cl:
                    centro = gm.value(subject=clog,predicate=ONTO.NombreCL)
                if priority == 1:
                    fecha =str(datetime.datetime.now() + datetime.timedelta(days=1))
                elif priority == 2:
                    fecha =str(datetime.datetime.now() + datetime.timedelta(days=random.randint(3,5)))
                elif priority == 3:
                    fecha =str(datetime.datetime.now() + datetime.timedelta(days=random.randint(5,10)))
                geolocator = Nominatim(user_agent='myapplication')
                location = geolocator.geocode(city)
                location = (location.latitude, location.longitude)
                if centro=="Barcelona":
                    dist_fromcentro = great_circle(location_bcn, location).km
                elif centro =="Pekin":
                    dist_fromcentro = great_circle(location_ny, location).km
                elif centro =="New York":
                    dist_fromcentro = great_circle(location_ny, location).km
                precio_envio= peso_total*50+0.10*dist_fromcentro
                count = get_count()
                subject = URIRef("http://www.owl-ontologies.com/OntologiaECSDI.owl#RespuestaTransportista_"+str(count))
                respuesta=Graph()
                respuesta.add((subject,RDF.type,ONTO.RespuestaTransportista))
                respuesta.add((subject,ONTO.Fecha,fecha))
                respuesta.add((subject,ONTO.PrecioTransporte,precio_envio))
                ref = URIRef("http://www.owl-ontologies.com/OntologiaECSDI.owl#Transportista_Nacex")
                respuesta.add((ref,RDF.type,ONTO.Transportista))
                respuesta.add((ref,ONTO.Nombre,"NACEX"))
                respuesta.add((ref,ONTO.Identificador,"Transportista_Nacex"))
                respuesta.add((subject,ONTO.Transportista,URIRef(ref)))
                return respuesta.serialize(format="xml"),200
            elif accion == ONTO.ConfirmarTransportista:
                grr = Graph()
                return grr.serialize(format="xml"),200


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