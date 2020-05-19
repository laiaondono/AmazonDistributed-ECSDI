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

import time, random
import argparse
import socket
import sys
import requests
from multiprocessing import Queue, Process
from flask import Flask, request
from pyparsing import Literal
from rdflib import URIRef, XSD, Namespace, Graph
from Util.ACLMessages import *
from Util.Agent import Agent
from Util.FlaskServer import shutdown_server
from Util.Logging import config_logger
from Util.OntoNamespaces import ONTO

__author__ = 'pau-laia-anna'
logger = config_logger(level=1)

# Configuration stuff
hostname = socket.gethostname()
port = 9010

agn = Namespace("http://www.agentes.org#")

# Contador de mensajes
mss_cnt = 0

# Datos del Agente

AgBuscadorProductos = Agent('AgBuscadorProductos',
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


def get_count():
    global mss_cnt
    mss_cnt += 1
    return mss_cnt


def test_suma():
    peticion = {"numero1": random.randint(0, 400), "numero2": random.randint(0, 400)}
    port_agprova = 9011
    uri = 'http://desktop-lrtmd2a:9011/sum'
    print(uri)
    print(peticion)
    headers = {'content-type': 'application/json'}
    r = requests.get(uri, params=peticion, headers=headers)
    print(r.text)
    return r.text


def busca():
    peticion = {"numero1": random.randint(0, 400), "numero2": random.randint(0, 400)}
    port_agprova = 9011
    uri = 'http://desktop-lrtmd2a:9011/sum'
    print(uri)
    print(peticion)
    headers = {'content-type': 'application/json'}
    r = requests.get(uri, params=peticion, headers=headers)
    print(r.text)
    return r.text




@app.route("/comm")
def communication():
    """
    Communication Entrypoint
    """

    logger.info('Peticion de informacion recibida')
    global dsGraph

    message = request.args['content']
    gm = Graph()
    gm.parse(data=message)

    msgdic = get_message_properties(gm)

    gr = None

    if msgdic is None:
        # Si no es, respondemos que no hemos entendido el mensaje
        gr = build_message(Graph(), ACL['not-understood'], sender=AgBuscadorProductos.uri, msgcnt=get_count())
    else:
        # Obtenemos la performativa
        if msgdic['performative'] != ACL.request:
            # Si no es un request, respondemos que no hemos entendido el mensaje
            gr = build_message(Graph(),
                               ACL['not-understood'],
                               sender=AgBuscadorProductos.uri,
                               msgcnt=get_count())
        else:
            # Extraemos el objeto del contenido que ha de ser una accion de la ontologia
            # de registro
            content = msgdic['content']
            # Averiguamos el tipo de la accion
            accion = gm.value(subject=content, predicate=RDF.type)

            # Accion de busqueda
            if accion == ONTO.BuscarProductos:
                restriccions = gm.objects(content, ONTO.RestringidaPor)
                restriccions_dict = {}
                for restriccio in restriccions:
                    if gm.value(subject=restriccio, predicate=RDF.type) == ONTO.RestriccionMarca:
                        marca = gm.value(subject=restriccio, predicate=ONTO.Marca)
                        logger.info('BÚSQUEDA->Restriccion de Marca: ' + marca)
                        restriccions_dict['marca'] = marca

                    elif gm.value(subject=restriccio, predicate=RDF.type) == ONTO.RestriccionPrecio:
                        preciomax = gm.value(subject=restriccio, predicate=ONTO.PrecioMaximo)
                        preciomin = gm.value(subject=restriccio, predicate=ONTO.PrecioMinimo)
                        if preciomin:
                            logger.info('BÚSQUEDA->Restriccion de precio minimo:' + preciomin)
                            restriccions_dict['preciomin'] = preciomin.toPython()
                        if preciomax:
                            logger.info('BÚSQUEDA->Restriccion de precio maximo:' + preciomax)
                            restriccions_dict['preciomax'] = preciomax.toPython()
                    elif gm.value(subject=restriccio, predicate=RDF.type) == ONTO.RestriccionNombre:
                        nombre = gm.value(subject=restriccio, predicate=ONTO.Nombre)
                        logger.info('BÚSQUEDA->Restriccion de Nombre: ' + nombre)
                        restriccions_dict['nombre'] = nombre
                    elif gm.value(subject=restriccio, predicate=RDF.type) == ONTO.RestriccionValoracion:
                        valoracion = gm.value(subject=restriccio, predicate=ONTO.Valoracion)
                        logger.info('BÚSQUEDA->Restriccion de Valoracion: ' + valoracion)
                        restriccions_dict['valoracion'] = valoracion

                gr = buscar_productos(**restriccions_dict)

            # Accion de comprar
            """
            elif accion == ECSDI.Peticion_compra:
                logger.info("He rebut la peticio de compra")

                sell = None
                for item in gm.subjects(RDF.type, ECSDI.Compra):
                    sell = item

                gm.remove((content, None, None))
                for item in gm.subjects(RDF.type, ACL.FipaAclMessage):
                    gm.remove((item, None, None))

                content = ECSDI['Vull_comprar_' + str(get_count())]
                gm.add((content, RDF.type, ECSDI.Vull_comprar))
                gm.add((content, ECSDI.compra, URIRef(sell)))
                gr = gm

                financial = get_agent_info(agn.FinancialAgent, DirectoryAgent, SellerAgent, get_count())

                gr = send_message(
                    build_message(gr, perf=ACL.request, sender=SellerAgent.uri, receiver=financial.uri,
                                  msgcnt=get_count(),
                                  content=content), financial.address)

            elif accion == ECSDI.Peticion_retorno:
                logger.info("He rebut la peticio de retorn")

                for item in gm.subjects(RDF.type, ACL.FipaAclMessage):
                    gm.remove((item, None, None))

                gr = gm


                financial = get_agent_info(agn.FinancialAgent, DirectoryAgent, SellerAgent, get_count())

                gr = send_message(
                    build_message(gr, perf=ACL.request, sender=SellerAgent.uri, receiver=financial.uri,
                                  msgcnt=get_count(),
                                  content=content), financial.address)

            # No habia ninguna accion en el mensaje
            else:
                gr = build_message(Graph(),
                                   ACL['not-understood'],
                                   sender=DirectoryAgent.uri,
                                   msgcnt=get_count())
            """
    logger.info('Respondemos a la peticion')
    serialize = gr.serialize(format='xml')
    return serialize, 200


@app.route("/searchtest")
def busca():
    """
    Entrypoint de comunicacion
    """
    graph = Graph()
    # WARNING: De moment no m'agafa el PATH relatiu, i li haig de posar l'absolut, s'ha de canviar depen de la màquina que ho executi.
    ontologyFile = open('/Users/pauca/Documents/GitHub/ECSDI_Practica/Protege/Ontologia.owl')
    graph.parse(ontologyFile, format='xml')
    query = """
        prefix rdf:<http://www.w3.org/1999/02/22-rdf-syntax-ns#>
        prefix xsd:<http://www.w3.org/2001/XMLSchema#>
        prefix default:<http://www.owl-ontologies.com/OntologiaECSDI.owl#>
        prefix owl:<http://www.w3.org/2002/07/owl#>
        SELECT DISTINCT ?producto ?nombre ?precio 
        where {
            { ?producto rdf:type default:Producto } UNION { ?producto rdf:type default:Producto_externo } .
            ?producto default:Nombre ?nombre .
            ?producto default:PrecioProducto ?precio
            FILTER(?precio <1000)
               }order by asc(UCASE(str(?nombre)))"""

    graph_query = graph.query(query)
    """
    result = Graph()
    result.bind('ONTO',ONTO)
    product_count=0
    for row in graph_query:
        nom = row.nombre
        model = row.modelo
        marca = row.marca
        preu = row.precio
        peso = row.peso
        logger.debug(nom, marca, model, preu)
        subject = row.producto
        product_count += 1
        result.add((subject, RDF.type, ONTO.Producte))
        result.add((subject, ONTO.Nombre, Literal(nom, datatype=XSD.string)))
    """
    """
g = Graph()
 
g.parse('C:/Users/pauca/Desktop/ECSDI/Ontologia.owl', format='xml')
name = Namespace('C:/Users/pauca/Desktop/ECSDI/Ontologia.owl')
#print(g.triples(None,FOAF.name,"hasdh"))

for s, p, o in g:
    if (str(s) == "http://www.semanticweb.org/pauca/ontologies/2020/3/untitled-ontology-4#Producto_5PLUYF"):
        print(str(p) + " : " +str(o))
    #print("Sujeto " + str(s))
    #print("Predicado " + str(p))
    #print("Objeto " + str(o))

node = URIRef('http://mundo.mundial.org/persona/pedro')

res = g.query( PREFIX foaf: <http://xmlns.com/foaf/0.1/>
                    SELECT DISTINCT ?a ?Nombre
                    WHERE {
                        ?a foaf:age ?PrecioProducto .
                        ?a foaf:name ?Nombre .
                        FILTER {?PrecioProducto > 18}
                        })
                        """
    result = []
    for row in graph_query:
        print(row)
        result.append(str(row.nombre) + "/" + str(row.precio))
    return str(result)


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

def buscar_productos(valoracion=0.0, marca=None, preciomin=0.0, preciomax=sys.float_info.max, nombre=None):
    graph = Graph()
    ontologyFile = open('/Users/pauca/Documents/GitHub/ECSDI_Practica/Protege/Ontologia.owl')
    graph.parse(ontologyFile, format='xml')

    first = second = 0
    query = """
        prefix rdf:<http://www.w3.org/1999/02/22-rdf-syntax-ns#>
        prefix xsd:<http://www.w3.org/2001/XMLSchema#>
        prefix default:<http://www.owl-ontologies.com/OntologiaECSDI.owl#>
        prefix owl:<http://www.w3.org/2002/07/owl#>
        SELECT DISTINCT ?producto ?nombre ?precio ?id ?marca
        where {
            { ?producto rdf:type default:Producto }.
            ?producto default:Nombre ?nombre .
            ?producto default:PrecioProducto ?precio .
            ?producto default:Marca ?marca .
            ?producto default:Identificador ?id 
            FILTER("""

    if nombre is not None:
        query += """str(?nombre) = '""" + nombre + """'"""
        first = 1
    #if valoracion is not None:
        #query += """str(?valoracion) = '""" + str(valoracion) + """'"""
    if marca is not None:
        if first==1:
            query += """ && """
        query += """str(?marca) = '""" + marca + """'"""
        second == 1
    if first==1 or second == 1:
        query += """ && """
    query += """?precio >= """ + str(preciomin) + """ &&
                ?precio <= """ + str(preciomax) + """  )}
                order by asc(UCASE(str(?nombre)))"""
    logger.info(query)
    graph_query = graph.query(query)
    result = Graph()
    # Aqui hi havia un bind
    product_count = 0
    for row in graph_query:
        logger.info(row.nombre)
        nom = row.nombre
        marca = row.marca
        precio = row.precio
        id = row.id
        logger.debug(id, nom, marca, valoracion, precio)
        subject = row.producto
        product_count += 1
        result.add((subject, RDF.type, ONTO.Producto))
        result.add((subject, ONTO.Marca, Literal(marca, datatype=XSD.string)))
        result.add((subject, ONTO.Valoracion, Literal(valoracion, datatype=XSD.float)))
        result.add((subject, ONTO.Precio, Literal(precio, datatype=XSD.float)))
        result.add((subject, ONTO.Identificador, Literal(id, datatype=XSD.string)))
        result.add((subject, ONTO.Nombre, Literal(nom, datatype=XSD.string)))
    return result




if __name__ == '__main__':
    # Ponemos en marcha los behaviors
    ab1 = Process(target=agentbehavior1, args=(cola1,))
    ab1.start()

    # Ponemos en marcha el servidor
    app.run(host=hostname, port=port)

    # Esperamos a que acaben los behaviors
    ab1.join()
    print('The End')
