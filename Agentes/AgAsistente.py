# -*- coding: utf-8 -*-
"""
Agente Buscador de productos.
Esqueleto de agente usando los servicios web de Flask

/comm es la entrada para la recepcion de mensajes del agente
/Stop es la entrada que para el agente

Tiene una funcion AgentBehavior1 que se lanza como un thread concurrente

Asume que el agente de registro esta en el puerto 9000

@author: pau-laia-anna
"""
from imaplib import Literal
from multiprocessing import Process, Queue
import socket

from rdflib import URIRef, Namespace, Graph, FOAF, RDF
from flask import Flask, request, render_template
import rdflib

from Agentes.SimpleDirectoryService import register_agent
from Util.ACLMessages import build_message, send_message
from Util.FlaskServer import shutdown_server
from Util.Agent import Agent
from Util.OntoNamespaces import DSO, ONTO, ACL

__author__ = 'pau-laia-anna'

# Configuration stuff
hostname = socket.gethostname()

port = 9011

agn = Namespace("http://www.agentes.org#")

# Contador de mensajes
mss_cnt = 0

# Datos del Agente

AgAsistente = Agent('AgAsistente',
                    agn.AgAsistente,
                    'http://%s:%d/comm' % (hostname, port),
                    'http://%s:%d/Stop' % (hostname, port))

# Directory agent address
DirectoryAgent = Agent('DirectoryAgent',
                       agn.Directory,
                       'http://%s:9000/Register' % hostname,
                       'http://%s:9000/Stop' % hostname)

AgBuscadorProductos = Agent('AgBuscadorProductos',
                            agn.AgBuscadorProductos,
                            'http://%s:9000/Search' % hostname,
                            'http://%s:9000/Stop' % hostname)

# Global triplestore graph
dsgraph = Graph()

cola1 = Queue()

resultats = []
# Flask stuff

app = Flask(__name__, template_folder='../templates')


@app.route("/sum")
def suma():
    num1 = request.args['numero1']
    num2 = request.args['numero2']
    resultats.append(int(num1) + int(num2))
    return str(int(num1) + int(num2))


@app.route("/comm")
def comunicacion():
    """
    Entrypoint de comunicacion
    """
    global dsgraph
    global mss_cnt
    return str(resultats)


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


@app.route("/search_products", methods=['GET', 'POST'])
def search_products():
    if request.method == 'GET':
        return render_template('search_products.html', products=None)
    else:
        if request.form['submit'] == 'Buscar':
            name = request.form['name']
            price = request.form['price']
            brand = request.form['brand']

            global mss_cnt
            g = Graph()

            action = ONTO['BuscarProductos_' + str(mss_cnt)]
            g.add(action, RDF.type, ONTO.BuscarProductos)

            if name:
                nameRestriction = ONTO['RestriccionNombre_' + str(mss_cnt)]
                g.add(nameRestriction, RDF.type, ONTO.RestriccionNombre)
                g.add(nameRestriction, ONTO.Nombre, Literal(name)) # datatype=XSD.string !??!!?!?!?

            if price:
                priceRestriction = ONTO['RestriccionPrecio_' + str(mss_cnt)]
                g.add(priceRestriction, RDF.type, ONTO.RestriccionPrecio)
                g.add(priceRestriction, ONTO.PrecioProducto, Literal(price)) # datatype=XSD.string !??!!?!?!?

            if brand:
                brandRestriction = ONTO['RestriccionMarca_' + str(mss_cnt)]
                g.add(brandRestriction, RDF.type, ONTO.RestriccionMarca)
                g.add(brandRestriction, ONTO.Marca, Literal(brand)) # datatype=XSD.string !??!!?!?!?

            msg = build_message(g, ACL.request, AgAsistente.uri, AgBuscadorProductos.uri, action, mss_cnt)
            mss_cnt += 1
            gproducts = send_message(msg, AgBuscadorProductos.address)

            products_list = []
            for s, p, o in gproducts:
                """ NOSTRE
                product['url'] = s
                product['name'] =
                product['price'] =
                product['brand'] =

                products_list.append(product)
                """

                """ GITHUB
                if s not in subject_pos:
                    subject_pos[s] = index
                    products_list.append({})
                    index += 1
                if s in subject_pos:
                    subject_dict = products_list[subject_pos[s]]
                    if p == RDF.type:
                        subject_dict['url'] = s
                    elif p == ONTO.Nombre:
                        subject_dict['name'] = o
                    elif p == ONTO.PrecioProducto:
                        subject_dict['price'] = o
                    elif p == ONTO.Marca:
                        subject_dict['brand'] = o
                    products_list[subject_pos[s]] = subject_dict
                    """

            return render_template('search_products.html', products=products_list)


def agentbehavior1():
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
