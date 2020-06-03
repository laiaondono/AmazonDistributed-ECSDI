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
                    if p == ONTO.ProductosCompra:
                        productos.append(str(o))
                    elif p == ONTO.PrecioTotal:
                        importe = float(o)
                    elif p == ONTO.TarjetaCredito:
                        tarjeta = str(o)
                    elif p == ONTO.DNI:
                        dni_usuario = str(o)
                    elif p == ONTO.LoteEntregado:
                        nombre_compra = str(o)
                RegistroEconomicoFile = open("../Data/RegistroEconomico")
                grafo_economico = Graph()
                grafo_economico.parse(RegistroEconomicoFile,format='xml')
                total_registros = 0
                global cuenta_sistema
                for s,p,o in grafo_economico:
                    if p == ONTO.Concepto:
                        total_registros+=1
                action = ONTO["RegistroEconomico_"+str(total_registros)]
                grafo_economico.add((action,RDF.type,ONTO.RegistroEconomico))
                grafo_economico.add((action,ONTO.CuentaOrigen,Literal(tarjeta)))
                grafo_economico.add((action,ONTO.CuentaDestino,Literal(cuenta_sistema)))
                grafo_economico.add((action,ONTO.Importe,Literal(importe)))
                grafo_economico.add((action,ONTO.DNI,Literal(dni_usuario)))
                grafo_economico.add((action,ONTO.Concepto,Literal(nombre_compra)))
                total_registros+=1
                RegistroEconomicoFile = open("../Data/RegistroEconomico",'wb')
                RegistroEconomicoFile.write(grafo_economico.serialize(format='turtle'))
                for product in productos:
                    if product[8] == "E":
                        ProductosExternosFile = open("../Data/ProductosExternos")
                        grafo_productos_externos = Graph()
                        grafo_productos_externos.parse(ProductosExternosFile,format='xml')
                        query= """
                            prefix rdf:<http://www.w3.org/1999/02/22-rdf-syntax-ns#>
                            prefix xsd:<http://www.w3.org/2001/XMLSchema#>
                            prefix default:<http://www.owl-ontologies.com/OntologiaECSDI.owl#>
                            prefix owl:<http://www.w3.org/2002/07/owl#>
                            SELECT DISTINCT ?producto ?id ?empresa ?precio
                            where {
                            { ?producto rdf:type default:Producto }.
                            ?producto default:Identificador ?id . 
                            ?producto default:Empresa ?empresa .
                            ?producto default:PrecioProducto ?precio
                            FILTER( ?id = '"""+str(product)+"""')}"""
                        grafo_productos_externos = grafo_productos_externos.query(query)
                        precio_producto = ""
                        identificador = ""
                        for row in grafo_productos_externos:
                            empresa = row.empresa
                            precio_producto = (row.precio)*-1
                            identificador = row.id
                            break
                        g = Graph()
                        action = ONTO["PagarVendedorExterno"]
                        g.add((action, RDF.type,ONTO.PagarVendedorExterno))
                        g.add((action,ONTO.Nombre, Literal(empresa)))
                        msg = build_message(g, ACL.request, AgServicioPago.uri, AgVendedorExterno.uri, action, mss_cnt)
                        mss_cnt += 1
                        gnumerocuenta= send_message(msg, AgGestorCompra.address)
                        numero_cuenta = ""
                        for s,p,o in gnumerocuenta:
                            if p == ONTO.NumeroCuenta:
                                numero_cuenta = str(numero_cuenta)
                                break
                        RegistroEconomicoFile = open("../Data/RegistroEconomico")
                        grafo_economico = Graph()
                        grafo_economico.parse(RegistroEconomicoFile,format='xml')
                        action = ONTO["RegistroEconomico_"+str(total_registros)]
                        grafo_economico.add((action,RDF.type,ONTO.RegistroEconomico))
                        grafo_economico.add((action,ONTO.CuentaOrigen,Literal(cuenta_sistema)))
                        grafo_economico.add((action,ONTO.CuentaDestino,Literal(numero_cuenta)))
                        grafo_economico.add((action,ONTO.Importe,Literal(precio_producto)))
                        grafo_economico.add((action,ONTO.DNI,Literal(empresa)))
                        grafo_economico.add((action,ONTO.Concepto,Literal(str(identificador))))
                graff = Graph()
                return graff.serialize(format='xml'),200






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


