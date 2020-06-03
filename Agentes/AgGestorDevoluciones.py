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

from multiprocessing import Process, Queue
import socket

import flask
from rdflib import Namespace, Graph, RDF, Literal, URIRef
from flask import Flask, request, render_template

from Util.ACLMessages import *
from Util.FlaskServer import shutdown_server
from Util.Agent import Agent
from Util.OntoNamespaces import ONTO, ACL
import datetime
from geopy.geocoders import Nominatim
from geopy.distance import geodesic, great_circle

__author__ = 'javier'


# Configuration stuff
hostname = socket.gethostname()
port = 9020

agn = Namespace("http://www.agentes.org#")

# Contador de mensajes
mss_cnt = 0

def get_count():
    global mss_cnt
    mss_cnt += 1
    return mss_cnt

# Datos del Agente

AgGestorDevoluciones = Agent('AgGestorDevoluciones',
                       agn.AgGestorDevoluciones,
                       'http://%s:%d/comm' % (hostname, port),
                       'http://%s:%d/Stop' % (hostname, port))

AgAsistente = Agent('AgAsistente',
                       agn.AgAsistente,
                       'http://%s:9011/comm' % hostname,
                       'http://%s:9011/Stop' % hostname)

AgServicioPago = Agent('AgServicioPago',
                    agn.AgServicioPago,
                    'http://%s:9019/comm' % hostname,
                    'http://%s:9019/Stop' % hostname)

AgVendedorExterno = Agent('AgVendedorExterno',
                       agn.AgVendedorExterno,
                       'http://%s:9018/comm' % hostname,
                       'http://%s:9018/Stop' % hostname)

# Global triplestore graph
dsgraph = Graph()

cola1 = Queue()

# Flask stuff
app = Flask(__name__)


location_ny = ( Nominatim(user_agent='myapplication').geocode("New York").latitude, Nominatim(user_agent='myapplication').geocode("New York").longitude)
location_bcn = (Nominatim(user_agent='myapplication').geocode("Barcelona").latitude,Nominatim(user_agent='myapplication').geocode("Barcelona").longitude)
location_pk = (Nominatim(user_agent='myapplication').geocode("Pekín").latitude,Nominatim(user_agent='myapplication').geocode("Pekín").longitude)



@app.route("/comm")
def comunicacion():
    """
    Entrypoint de comunicacion
    """
    global dsgraph, fecha, city, tarjcredito, precio
    global mss_cnt

    message = request.args['content']
    gm = Graph()
    gm.parse(data=message)

    msgdic = get_message_properties(gm)

    gr = None
    global mss_cnt
    if msgdic is None:
        mss_cnt+=1
        # Si no es, respondemos que no hemos entendido el mensaje
        gr = build_message(Graph(), ACL['not-understood'], sender=AgAsistente.uri, msgcnt=str(mss_cnt))
    else:
        # Obtenemos la performativa
        if msgdic['performative'] != ACL.request:
            # Si no es un request, respondemos que no hemos entendido el mensaje
            gr = build_message(Graph(),
                               ACL['not-understood'],
                               sender=AgAsistente.uri,
                               msgcnt=str(mss_cnt))
        else:
            # Extraemos el objeto del contenido que ha de ser una accion de la ontologia
            # de registro
            content = msgdic['content']
            # Averiguamos el tipo de la accion
            accion = gm.value(subject=content, predicate=RDF.type)

            if accion == ONTO.DevolverProducto:

                for s, p, o in gm:
                    if p == ONTO.MotivoDevolucion:
                        motivo = int(o)
                    if p == ONTO.CompraDevolucion:
                        idcompra = o.toPython()

                if motivo == 3:
                    PedidosFile = open('../Data/RegistroPedidos')
                    g = Graph()
                    g.parse(PedidosFile, format='turtle')
                    query ="""prefix rdf:<http://www.w3.org/1999/02/22-rdf-syntax-ns#>
                    prefix xsd:<http://www.w3.org/2001/XMLSchema#>
                    prefix default:<http://www.owl-ontologies.com/OntologiaECSDI.owl#>
                    prefix owl:<http://www.w3.org/2002/07/owl#>
                    SELECT DISTINCT ?fecha
                    where {
                        { ?compra rdf:type default:Compra }.
                        ?compra default:FechaEntrega ?fecha .
                        ?compra default:Lote ?idcompra .
                    FILTER( str(?idcompra) = '""" + str(idcompra) +"""')}"""
                    g = g.query(query)
                    for node in g:
                        fecha = node.fecha

                    fechaCompra = datetime.datetime.strptime(fecha, '%Y-%m-%d %H:%M:%S.%f')
                    dias_pasados = fechaCompra - datetime.datetime.now()
                    if dias_pasados.seconds > 30: #TODO mirar unitats --> posar 30 segons
                        g = Graph()
                        g.add((accion, RDF.type, ONTO.DevolverProducto))
                        return g.serialize(format="xml"),200

                g = Graph()
                PedidosFile = open('../Data/RegistroPedidos')
                g.parse(PedidosFile, format='turtle')
                query ="""prefix rdf:<http://www.w3.org/1999/02/22-rdf-syntax-ns#>
                prefix xsd:<http://www.w3.org/2001/XMLSchema#>
                prefix default:<http://www.owl-ontologies.com/OntologiaECSDI.owl#>
                prefix owl:<http://www.w3.org/2002/07/owl#>
                SELECT DISTINCT ?city
                where {
                    { ?compra rdf:type default:Compra }.
                    ?compra default:Ciudad ?city .
                    ?compra default:Lote ?idcompra .
                FILTER( str(?idcompra) = '""" + str(idcompra) +"""')}"""
                g = g.query(query)
                for node in g:
                    city = node.city

                geolocator = Nominatim(user_agent='myapplication')
                location = geolocator.geocode(city)
                location = (location.latitude, location.longitude)
                dist_bcn =  great_circle(location_bcn, location).km
                dist_ny = great_circle(location_ny, location).km
                dist_pk = great_circle(location_pk, location).km
                if dist_bcn < dist_ny and dist_bcn < dist_pk:
                    direccionenvio = "Barcelona"
                elif dist_ny < dist_pk:
                    direccionenvio = "New York"
                else:
                    direccionenvio = "Pekin"

                gInfo = Graph()
                gInfo.add((accion, RDF.type, ONTO.DevolverProducto))
                gInfo.add((accion, ONTO.DireccionEnvio, Literal(direccionenvio)))
                gInfo.add((accion, ONTO.EmpresaMensajeria, Literal("Correos")))

                return gInfo.serialize(format="xml"), 200

            if accion == ONTO.FinalizarDevolucion:
                for s, p, o in gm:
                    if p == ONTO.CompraDevolucion:
                        idcompra = ONTO[str(o)]
                    if p == ONTO.ProductoADevolver:
                        producto = str(o)

                PedidosFile = open('../Data/RegistroPedidos')
                g = Graph()
                g.parse(PedidosFile, format='turtle')
                for s, p, o in g:
                    if p == ONTO.TarjetaCredito and str(s) == str(idcompra):
                        tarjcredito = str(o)

                gr = Graph()
                for s, p, o in g:
                    if str(s) != str(idcompra) and str(o) != str(producto):
                        gr.add((s, p, o))

                #PedidosFile = open('../Data/RegistroPedidos', 'wb') #TODO
                #PedidosFile.write(gr.serialize(format='turtle'))

                ProductosFile = open('../Data/Productos')
                g = Graph()
                g.parse(ProductosFile, format='xml')
                es_ext = True
                for s, p, o in g:
                    if p == ONTO.Nombre and str(o) == str(producto):
                        precio = g.value(subject=s, predicate=ONTO.PrecioProducto)
                        es_ext = False
                        break

                if es_ext:
                    ProductosFile = open('../Data/ProductosExternos')
                    g = Graph()
                    g.parse(ProductosFile, format='xml')
                    for s, p, o in g:
                        if p == ONTO.Nombre and str(o) == str(producto):
                            precio = g.value(subject=s, predicate=ONTO.PrecioProducto)
                            empresa = g.value(subject=s, predicate=ONTO.Empresa)
                            idprodext = g.value(subject=s, predicate=ONTO.Identificador)
                            break

                gDevolucion = Graph()
                accion = ONTO["DevolverDinero_" + str(get_count())]
                gDevolucion.add((accion, RDF.type, ONTO.DevolverDinero))
                gDevolucion.add((accion, ONTO.Destino, Literal(tarjcredito)))
                gDevolucion.add((accion, ONTO.Origen, Literal("ESBN8377228748")))
                for s, p, o in gm:
                    if p == ONTO.DevueltoPor:
                        nombreusuario = str(o)
                gDevolucion.add((accion, ONTO.Usuario, Literal(nombreusuario)))
                gDevolucion.add((accion, ONTO.Importe, Literal(precio)))
                compra = idcompra[49:]
                gDevolucion.add((accion, ONTO.Compra, Literal(compra)))

                msg = build_message(gDevolucion, ACL.request, AgGestorDevoluciones.uri, AgServicioPago.uri, accion, mss_cnt)
                send_message(msg, AgServicioPago.address)

                if es_ext:

                    ginfovendedor = Graph()
                    accion = ONTO["CobrarVendedorExterno_" + str(get_count())]
                    ginfovendedor.add((accion, RDF.type, ONTO.CobrarVendedorExterno))
                    ginfovendedor.add((accion, ONTO.Nombre, Literal(empresa)))
                    msg = build_message(ginfovendedor, ACL.request, AgGestorDevoluciones.uri, AgVendedorExterno.uri, accion, mss_cnt)
                    gcuentabancaria = send_message(msg, AgVendedorExterno.address)
                    for s, p, o in gcuentabancaria:
                        if p == ONTO.CuentaBancaria:
                            cbempresa = str(o)

                    g = Graph()
                    g.add((accion, RDF.type, ONTO.CobrarVendedorExterno))
                    g.add((accion, ONTO.Origen, Literal(cbempresa)))
                    g.add((accion, ONTO.Usuario, Literal(empresa)))
                    g.add((accion, ONTO.Destino, Literal("ESBN8377228748")))
                    g.add((accion, ONTO.Importe, Literal(precio)))
                    g.add((accion, ONTO.Concepto, Literal(idprodext)))

                    msg = build_message(g, ACL.request, AgGestorDevoluciones.uri, AgServicioPago.uri, accion, mss_cnt)
                    send_message(msg, AgServicioPago.address)

                grr = Graph()
                return grr.serialize(format="xml"), 200













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


