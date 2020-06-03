# -*- coding: utf-8 -*-
"""
Created on Fri Dec 27 15:58:13 2013

Esqueleto de agente usando los servicios web de Flask

/comm es la entrada para la recepcion de mensajes del agente
/Stop es la entrada que para el agente

Tiene una funcion AgentBehavior1 que se lanza como un thread concurrente

Asume que el agente de registro esta en el puerto 9000

@author: javier
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

__author__ = 'javier'
logger = config_logger(level=1)

# Configuration stuff
hostname = socket.gethostname()
port = 9019

agn = Namespace("http://www.agentes.org#")

# Contador de mensajes
mss_cnt = 0

cuenta_sistema = "ESBN8377228748"
# Datos del Agente
AgServicioPago = Agent('AgServicioPago',
                       agn.AgServicioPago,
                       'http://%s:%d/comm' % (hostname, port),
                       'http://%s:%d/Stop' % (hostname, port))

AgGestorCompra = Agent('AgGestorCompra',
                       agn.AgGestorCompra,
                       'http://%s:9012/comm' % hostname,
                       'http://%s:9012/Stop' % hostname)

AgVendedorExterno = Agent('AgVendedorExterno',
                       agn.AgVendedorExterno,
                       'http://%s:9018/comm' % hostname,
                       'http://%s:9018/Stop' % hostname)

# Global triplestore graph
dsgraph = Graph()
graff = Graph()
cola1 = Queue()

# Flask stuff
app = Flask(__name__)


def get_count():
    global mss_cnt
    mss_cnt += 1
    return mss_cnt

@app.route("/comm")
def comunicacion():
    """
    Entrypoint de comunicacion
    """
    global dsgraph, graff
    global mss_cnt
    message = request.args['content']
    gm = Graph()
    gm.parse(data=message)

    msgdic = get_message_properties(gm)

    gr = None
    if msgdic is None:
        # Si no es, respondemos que no hemos entendido el mensaje
        gr = build_message(Graph(), ACL['not-understood'], sender=AgServicioPago.uri, msgcnt=get_count())
    else:
        global cuenta_sistema
        # Obtenemos la performativa
        if msgdic['performative'] != ACL.request:
            # Si no es un request, respondemos que no hemos entendido el mensaje
            gr = build_message(Graph(),
                               ACL['not-understood'],
                               sender=AgServicioPago.uri,
                               msgcnt=get_count())
        else:
            # Extraemos el objeto del contenido que ha de ser una accion de la ontologia
            # de registro
            content = msgdic['content']
            # Averiguamos el tipo de la accion
            accion = gm.value(subject=content, predicate=RDF.type)

            if accion == ONTO.CobrarCompra:
                dni_usuario = ""
                importe = 0.0
                tarjeta = ""
                productos = []
                empresa = ""
                nombre_compra = ""
                for s,p,o in gm:
                    #if p == ONTO.ProductosCompra:
                        #productos.append(str(o))
                    if p == ONTO.PrecioTotal:
                        importe = float(o)
                    elif p == ONTO.TarjetaCredito:
                        tarjeta = str(o)
                    elif p == ONTO.DNI:
                        dni_usuario = str(o)
                    elif p == ONTO.LoteEntregado:
                        nombre_compra = str(o)
                RegistroEconomicoFile = open("C:/Users/pauca/Documents/GitHub/ECSDI_Practica/Data/RegistroEconomico")
                grafo_economico = Graph()
                grafo_economico.parse(RegistroEconomicoFile,format='turtle')
                total_registros = 0
                for s,p,o in grafo_economico:
                    if p == ONTO.Concepto:
                        total_registros+=1
                action = ONTO["RegistroEconomico_"+str(total_registros)]
                grafo_economico.add((action,RDF.type,ONTO.RegistroEconomico))
                grafo_economico.add((action,ONTO.CuentaOrigen,Literal(tarjeta,datatype=XSD.string)))
                grafo_economico.add((action,ONTO.CuentaDestino,Literal(cuenta_sistema,datatype=XSD.string)))
                grafo_economico.add((action,ONTO.Importe,Literal(importe,datatype=XSD.float)))
                grafo_economico.add((action,ONTO.DNI,Literal(dni_usuario,datatype=XSD.string)))
                grafo_economico.add((action,ONTO.Concepto,Literal(nombre_compra,datatype=XSD.string)))
                total_registros+=1

                RegistroEconomicoFile = open("C:/Users/pauca/Documents/GitHub/ECSDI_Practica/Data/RegistroEconomico",'wb')
                RegistroEconomicoFile.write(grafo_economico.serialize(format='turtle'))
                RegistroEconomicoFile.close()
                logger.info("Compra registrada")
                graff = Graph()
                return graff.serialize(format='xml'),200

            elif accion == ONTO.PagarVendedorExterno:

                dni_usuario = ""
                importe = 0.0
                cuenta_destino = ""
                productos = []
                empresa = ""
                nombre_compra = ""
                for s,p,o in gm:
                    #if p == ONTO.ProductosCompra:
                    #productos.append(str(o))
                    if p == ONTO.PrecioTotal:
                        importe = float(o)*-1
                    elif p == ONTO.CuentaDestino:
                        tarjeta = str(o)
                    elif p == ONTO.DNI:
                        dni_usuario = str(o)
                    elif p == ONTO.NombreProducto:
                        nombre_compra = str(o)
                RegistroEconomicoFile = open("C:/Users/pauca/Documents/GitHub/ECSDI_Practica/Data/RegistroEconomico")
                grafo_economico = Graph()
                grafo_economico.parse(RegistroEconomicoFile,format='turtle')
                total_registros = 0
                for s,p,o in grafo_economico:
                    if p == ONTO.Concepto:
                        total_registros+=1
                action = ONTO["RegistroEconomico_"+str(total_registros)]
                grafo_economico.add((action,RDF.type,ONTO.RegistroEconomico))
                grafo_economico.add((action,ONTO.CuentaOrigen,Literal(cuenta_sistema,datatype=XSD.string)))
                grafo_economico.add((action,ONTO.CuentaDestino,Literal(tarjeta,datatype=XSD.string)))
                grafo_economico.add((action,ONTO.Importe,Literal(importe,datatype=XSD.float)))
                grafo_economico.add((action,ONTO.DNI,Literal(dni_usuario,datatype=XSD.string)))
                grafo_economico.add((action,ONTO.Concepto,Literal(nombre_compra,datatype=XSD.string)))
                total_registros+=1
                RegistroEconomicoFile = open("C:/Users/pauca/Documents/GitHub/ECSDI_Practica/Data/RegistroEconomico",'wb')
                RegistroEconomicoFile.write(grafo_economico.serialize(format='turtle'))
                RegistroEconomicoFile.close()
                logger.info("Producto pagado a empresa externa")
                graff = Graph()
                return graff.serialize(format='xml'),200

            if accion == ONTO.DevolverDinero:
                RegistroEconomicoFile = open('../Data/RegistroEconomico')
                g = Graph()
                g.parse(RegistroEconomicoFile, format='xml') #TODO ojo format
                total_registros = 0
                for s, p, o in g:
                    if p == ONTO.Concepto:
                        total_registros+=1

                gNuevaTransferencia = Graph()
                action = ONTO["RegistroEconomico_" + str(total_registros)]
                gNuevaTransferencia.add((action, RDF.type, ONTO.RegistroEconomico))
                origen = gm.value(subject=accion, predicate=ONTO.Origen)
                gNuevaTransferencia.add((action,ONTO.CuentaOrigen, Literal(origen)))
                destino = gm.value(subject=accion, predicate=ONTO.Destino)
                gNuevaTransferencia.add((action,ONTO.CuentaDestino,Literal(destino)))
                precio = gm.value(subject=accion, predicate=ONTO.Importe) * -1 #TODO comprovar que funciona
                gNuevaTransferencia.add((action,ONTO.Importe,Literal(precio)))
                dni = gm.value(subject=accion, predicate=ONTO.Usuario)
                gNuevaTransferencia.add((action,ONTO.DNI,Literal(dni)))
                concepto = gm.value(subject=accion, predicate=ONTO.Compra)
                gNuevaTransferencia.add((action,ONTO.Concepto,Literal(concepto)))
                g += gNuevaTransferencia
                total_registros += 1

                RegistroEconomicoFile = open('../Data/RegistroEconomico', 'wb')
                RegistroEconomicoFile.write(g.serialize(format='turtle'))
                graff = Graph()
                return graff.serialize(format='xml'),200



"""
ns1:RegistroEconomico_0 a ns1:RegistroEconomico ;
    ns1:Concepto "Compra_2"^^xsd:string ;
    ns1:CuentaDestino "ESBN8377228748"^^xsd:string ;
    ns1:CuentaOrigen "ESBN1235453"^^xsd:string ;
    ns1:DNI "423121121E"^^xsd:string ;
    ns1:Importe "250.0"^^xsd:float .
    """




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


