# -*- coding: utf-8 -*-
"""
Agente Buscador de productos.
Esqueleto de agente usando los servicios web de Flask

/comm es la entrada para la recepcion de mensajes del agente
/Stop es la entrada que para el agente

Tiene una funcion AgentBehavior1 que se lanza como un thread concurrente

@author: pau-laia-anna
"""

import random
import socket
import sys
from multiprocessing import Queue, Process
from flask import Flask, request
from pyparsing import Literal
from rdflib import XSD, Namespace, Literal, URIRef
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

            # Accion de buscar productos
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

    return gr.serialize(format='xml'), 200


@app.route("/searchtest")
def busca():
    """
    Entrypoint de comunicacion
    """
    graph = Graph()
    # WARNING: De moment no m'agafa el PATH relatiu, i li haig de posar l'absolut, s'ha de canviar depen de la màquina que ho executi.
    ontologyFile = open('../Data/Productos')
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
            FILTER(?precio <10000)
               }order by asc(UCASE(str(?nombre)))"""

    graph_query = graph.query(query)
    result = []
    for row in graph_query:
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

def añadir_productos():
    graph = Graph()
    ontologyFile = open('../Data/Productos')
    graph.parse(ontologyFile, format='xml')

    for i in range(30):
        subject = URIRef("http://www.owl-ontologies.com/OntologiaECSDI.owl#Producto_5PLUYF"+ str(random.randint(1000,20000)))
        graph.add((subject, RDF.type, ONTO.Producto))
        graph.add((subject, ONTO.Marca, Literal("Nike", datatype=XSD.string)))
        graph.add((subject, ONTO.Valoracion, Literal(0.0, datatype=XSD.float)))
        graph.add((subject, ONTO.PrecioProducto, Literal(random.randint(1000, 2000), datatype=XSD.float)))
        graph.add((subject, ONTO.Identificador, Literal(str(random.randint(1000, 2000)), datatype=XSD.string)))
        graph.add((subject, ONTO.Nombre, Literal("Producto_5PLUYF"+str(random.randint(1000,20000)), datatype=XSD.string)))
    result = []
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
            FILTER(?precio <10000)
               }order by asc(UCASE(str(?nombre)))"""

    graph_query = graph.query(query)
    count = 0
    for row in graph_query:
        count+=1
        result.append(str(row.nombre) + "/" + str(row.precio))
    ofile  = open('../Data/Productos', "wb")
    ofile.write(graph.serialize(format='xml'))
    ofile.close()
    return str(result)


def buscar_productos(valoracion=0.0, marca=None, preciomin=0.0, preciomax=sys.float_info.max, nombre=None):
    graph = Graph()
    ontologyFile = open('../Data/Productos')
    graph.parse(ontologyFile, format='xml')

    first = second = 0
    query = """
        prefix rdf:<http://www.w3.org/1999/02/22-rdf-syntax-ns#>
        prefix xsd:<http://www.w3.org/2001/XMLSchema#>
        prefix default:<http://www.owl-ontologies.com/OntologiaECSDI.owl#>
        prefix owl:<http://www.w3.org/2002/07/owl#>
        SELECT DISTINCT ?producto ?nombre ?precio ?id ?marca ?peso ?valoracion
        where {
            { ?producto rdf:type default:Producto }.
            ?producto default:Nombre ?nombre .
            ?producto default:PrecioProducto ?precio .
            ?producto default:Marca ?marca .
            ?producto default:Identificador ?id . 
            ?producto default:Peso ?peso .
            ?producto default:Valoracion ?valoracion .
            FILTER("""

    if nombre is not None:
        query += """str(?nombre) = '""" + nombre + """'"""
        first = 1

    if valoracion is not None:
        if first == 1:
            query+=""" && """
        query += """str(?valoracion) >= '""" + str(valoracion) + """'"""
        first = 1

    if marca is not None:
        if first == 1:
            query += """ && """
        query += """str(?marca) = '""" + marca + """'"""
        second = 1

    if first == 1 or second == 1:
        query += """ && """

    query += """?precio >= """ + str(preciomin) + """ &&
                ?precio <= """ + str(preciomax) + """  )}
                order by asc(UCASE(str(?nombre)))"""

    graph_query = graph.query(query)
    result = Graph()
    product_count = 0
    for row in graph_query:
        nom_prod = row.nombre
        marca_prod = row.marca
        precio_prod = row.precio
        peso_prod = row.peso
        id_prod = row.id
        subject_prod = row.producto
        valoracion_prod = row.valoracion
        product_count += 1
        result.add((subject_prod, RDF.type, ONTO.Producto))
        result.add((subject_prod, ONTO.Marca, Literal(marca_prod, datatype=XSD.string)))
        result.add((subject_prod, ONTO.PrecioProducto, Literal(precio_prod, datatype=XSD.float)))
        result.add((subject_prod, ONTO.Identificador, Literal(id_prod, datatype=XSD.string)))
        result.add((subject_prod, ONTO.Nombre, Literal(nom_prod, datatype=XSD.string)))
        result.add((subject_prod, ONTO.Peso, Literal(peso_prod, datatype=XSD.float)))
        result.add((subject_prod, ONTO.Valoracion, Literal(valoracion_prod, datatype=XSD.float)))

    graphexternos = Graph()
    ontologyFileExtern = open('../Data/ProductosExternos')
    graphexternos.parse(ontologyFileExtern, format='xml')
    first = second = 0
    query = """
        prefix rdf:<http://www.w3.org/1999/02/22-rdf-syntax-ns#>
        prefix xsd:<http://www.w3.org/2001/XMLSchema#>
        prefix default:<http://www.owl-ontologies.com/OntologiaECSDI.owl#>
        prefix owl:<http://www.w3.org/2002/07/owl#>
        SELECT DISTINCT ?producto ?nombre ?precio ?id ?marca ?peso ?valoracion
        where {
            { ?producto rdf:type default:Producto }.
            ?producto default:Nombre ?nombre .
            ?producto default:PrecioProducto ?precio .
            ?producto default:Marca ?marca .
            ?producto default:Identificador ?id . 
            ?producto default:Peso ?peso .
            ?producto default:Valoracion ?valoracion .
            FILTER("""

    if nombre is not None:
        query += """str(?nombre) = '""" + nombre + """'"""
        first = 1

    if valoracion is not None:
        if first == 1:
            query += """ && """
        query += """str(?valoracion) >= '""" + str(valoracion) + """'"""
        first = 1

    if marca is not None:
        if first == 1:
            query += """ && """
        query += """str(?marca) = '""" + marca + """'"""
        second = 1

    if first == 1 or second == 1:
        query += """ && """

    query += """?precio >= """ + str(preciomin) + """ &&
                ?precio <= """ + str(preciomax) + """  )}
                order by asc(UCASE(str(?nombre)))"""

    graph_query_externos = graphexternos.query(query)
    product_count = 0
    for row in graph_query_externos:
        nom = row.nombre
        marca = row.marca
        precio = row.precio
        peso = row.peso
        id = row.id
        subject = row.producto
        valoracion = row.valoracion
        product_count += 1
        result.add((subject, RDF.type, ONTO.Producto))
        result.add((subject, ONTO.Marca, Literal(marca, datatype=XSD.string)))
        result.add((subject, ONTO.PrecioProducto, Literal(precio, datatype=XSD.float)))
        result.add((subject, ONTO.Identificador, Literal(id, datatype=XSD.string)))
        result.add((subject, ONTO.Nombre, Literal(nom, datatype=XSD.string)))
        result.add((subject, ONTO.Peso, Literal(peso, datatype=XSD.float)))
        result.add((subject, ONTO.Valoracion, Literal(valoracion, datatype=XSD.float)))

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
