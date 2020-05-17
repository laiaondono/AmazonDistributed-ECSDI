"""
.. module:: Agent

Agent
******

:Description: Agent
  Clase para guardar los atributos de un agente

"""

__author__ = 'pau-laia-anna'


class Agent():
    def __init__(self, name, uri, address, stop):
        self.name = name
        self.uri = uri
        self.address = address
        self.stop = stop