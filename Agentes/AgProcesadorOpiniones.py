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
import time
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
                PedidosFile = open('C:/Users/pauca/Documents/GitHub/ECSDI_Practica/Data/Historial')
                graphfinal = Graph()
                graphfinal.parse(PedidosFile, format='turtle')
                dni =""
                total_products = 0
                for s,p,o in graphfinal:
                    if p == ONTO.Identificador:
                        total_products+=1
                for s,p,o in gm:
                    if (p == ONTO.DNI):
                        dni = str(o)
                        break
                count = total_products
                for s,p,o in gm:
                    if p == ONTO.Identificador:
                        count+=1
                        historial = ONTO["Historial_" + str(count)]
                        graphfinal.add((historial,RDF.type,ONTO.Historial))
                        graphfinal.add((historial,ONTO.Identificador,Literal(str(o))))
                        graphfinal.add((historial,ONTO.DNI,Literal(str(dni))))
                PedidosFile = open('C:/Users/pauca/Documents/GitHub/ECSDI_Practica/Data/Historial', 'wb')
                PedidosFile.write(graphfinal.serialize(format='turtle'))
                PedidosFile.close()
                return gr.serialize(format="xml"),200

            if accion == ONTO.ValorarProducto:
                # Avisamos al AgAsistente de que ya se puede realizar la valoracion de los productos del grafo
                empezar_proceso = Process(target=Valorar, args=(gm,accion))
                empezar_proceso.start()

                #Returnem ACK al AgGestorCompra conforme ho hem rebut
                grr = Graph()
                return grr.serialize(format="xml"),200

def Valorar(gm, accion):
    msg = build_message(gm, ACL.request, AgProcesadorOpiniones.uri, AgAsistente.uri, accion, get_count())
    send_message(msg, AgAsistente.address)
    return

def recomendar():
    time.sleep(1)
    PedidosFile = open('C:/Users/pauca/Documents/GitHub/ECSDI_Practica/Data/Historial')
    historial = Graph()
    historial.parse(PedidosFile, format='turtle')
    ProductosFile = open("C:/Users/pauca/Documents/GitHub/ECSDI_Practica/Data/Productos")
    ProductosExternosFile = open("C:/Users/pauca/Documents/GitHub/ECSDI_Practica/Data/ProductosExternos")
    grafo_productos = Graph()
    grafo_productos.parse(ProductosFile,format='xml')
    grafo_productos_externos = Graph()
    grafo_productos_externos.parse(ProductosExternosFile,format='xml')
    usuarios = []
    for s,p,o in historial:
        if p == ONTO.DNI:
            if str(o) not in usuarios:
                usuarios.append(str(o))
    productos_usuario = []
    for p in usuarios:
        dic = {'categoria':"",'preciomedio':0.0,'usuario':p}
        productos_usuario.append(dic)
    subjects_user = []
    for prod in productos_usuario:
        cat_home = 0
        cat_deportes = 0
        cat_tecnologia = 0
        cat_otros = 0
        precio_medio = 0
        numero_precios = 0
        print(p)
        for s,p,o in historial:
            if p == ONTO.DNI:
                if prod['usuario']==str(o):
                    subjects_user.append(str(s))
        print(subjects_user)
        for s,p,o in historial:
            ProductosFile = open("C:/Users/pauca/Documents/GitHub/ECSDI_Practica/Data/Productos")
            ProductosExternosFile = open("C:/Users/pauca/Documents/GitHub/ECSDI_Practica/Data/ProductosExternos")
            grafo_productos = Graph()
            grafo_productos_externos = Graph()
            grafo_productos.parse(ProductosFile,format='xml')
            grafo_productos_externos.parse(ProductosExternosFile,format='xml')
            if str(s) in subjects_user and p == ONTO.Identificador:
                query = """
                    prefix rdf:<http://www.w3.org/1999/02/22-rdf-syntax-ns#>
                    prefix xsd:<http://www.w3.org/2001/XMLSchema#>
                    prefix default:<http://www.owl-ontologies.com/OntologiaECSDI.owl#>
                    prefix owl:<http://www.w3.org/2002/07/owl#>
                    SELECT DISTINCT ?producto ?id ?categoria ?precio
                    where {
                        { ?producto rdf:type default:Producto }.
                        ?producto default:Identificador ?id . 
                        ?producto default:Categoria ?categoria .
                        ?producto default:PrecioProducto ?precio .
                        FILTER( ?id = '"""+str(o)+"""')}"""
                grafo_productos = grafo_productos.query(query)
                grafo_productos_externos = grafo_productos_externos.query(query)
                for row in grafo_productos:
                    if str(row.categoria) == "Hogar":
                        cat_home+=1
                    elif str(row.categoria) == "Tecnologia":
                        cat_tecnologia+=1
                    elif str(row.categoria) == "Otros":
                        cat_otros+=1
                    elif str(row.categoria)=="Deporte":
                        cat_deportes+=1
                    if float(row.precio) > 0:
                        precio_medio = (precio_medio*numero_precios+float(row.precio))/(numero_precios+1)
                        numero_precios+=1
                for row in grafo_productos_externos:
                    if str(row.categoria) == "Hogar":
                        cat_home+=1
                    elif str(row.categoria) == "Tecnologia":
                        cat_tecnologia+=1
                    elif str(row.categoria) == "Otros":
                        cat_otros+=1
                    elif str(row.categoria)=="Deporte":
                        cat_deportes+=1
                    if float(row.precio) > 0:
                        precio_medio = (precio_medio*numero_precios+float(row.precio))/(numero_precios+1)
                        numero_precios+=1
        print(prod['usuario'])
        print("home "+str(cat_home))
        print("tec "+str(cat_tecnologia))
        print("otros "+str(cat_otros))
        print("dep "+str(cat_deportes))
        if cat_deportes > cat_otros and cat_deportes > cat_tecnologia and cat_deportes > cat_home:
            prod['categoria'] = 'Deporte'
        elif cat_otros > cat_deportes and cat_otros > cat_tecnologia and cat_otros > cat_home:
            prod['categoria'] = 'Otros'
        elif cat_tecnologia > cat_deportes and cat_tecnologia > cat_otros and cat_tecnologia > cat_home:
            prod['categoria'] = 'Tecnologia'
        else:
            prod['categoria'] = 'Hogar'
        prod['preciomedio'] = precio_medio
    print(productos_usuario)


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
    recomendar_automaticamente = Process(target=recomendar,args=())
    recomendar_automaticamente.start()

    # Ponemos en marcha el servidor
    app.run(host=hostname, port=port)

    # Esperamos a que acaben los behaviors
    ab1.join()
    print('The End')




