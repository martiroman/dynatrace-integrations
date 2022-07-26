#!/usr/bin/env python
"""
Integracion Nagios-Dynatrace:
Consulta los datos de hosts de Nagios a traves de MK-Livestatus y envia las metricas a Dynatrace creando el CUSTOM DEVICE
en caso de no existir

Dynatrace Type Events:
    AVAILABILITY_EVENT
    CUSTOM_ALERT
    CUSTOM_ANNOTATION
    CUSTOM_CONFIGURATION
    CUSTOM_DEPLOYMENT
    CUSTOM_INFO
    ERROR_EVENT
    MARKED_FOR_TERMINATION
    PERFORMANCE_EVENT
    RESOURCE_CONTENTION_EVENT
"""

import time
import sched
import json
import App.DynatraceApp as Dyna
import App.NagiosApp as Nagios
import App.IntegrationErrors as IntegrationErrors

with open('/etc/dynatrace-integrations/config.json', 'r') as file: config = json.load(file)

HOST_WHITELIST = config["NAGIOS"]["HOST_WHITELIST"]
SERVICE_WHITELIST = config["NAGIOS"]["SERVICE_WHITELIST"]

class Integracion(object):
    def __init__(self):
        self.NagiosConn = Nagios.Connection(config["NAGIOS"]["NAGIOS_SOCKET"])
        self.DynaConn = Dyna.Connection(config["DYNATRACE"]["API_URL"], config["DYNATRACE"]["API_TOKEN"])

    def CargarHosts(self):
        '''Obtiene el listado de hosts a monitorear'''
        favicon = "http://assets.dynatrace.com/global/icons/infographic_rack.png"
        tmpHosts = self.NagiosConn.getHosts()
        
        for host in tmpHosts:
            if (HOST_WHITELIST and host["name"] in HOST_WHITELIST) or not HOST_WHITELIST:
                #TODO: Configurar puertos del host
                dHost = self.DynaConn.addCustomHost(host['name'], host['address'], ['80','8080','443','8428','9100','9104','53862','53852'], 'Nagios', favicon, '', host['groups'][0])
                dHost.addTag(host['groups'])

    def CargarMetricas(self):
        '''Consulta los servicios de Nagios y asigna cada una de las metricas a los CustomHosts'''

        for host in self.DynaConn.getHosts():
            lstServices = []
            lstTmpServices = self.NagiosConn.getMetricas(host.displayName)
            for nagServ in lstTmpServices:
                if (SERVICE_WHITELIST and nagServ["service_description"] in SERVICE_WHITELIST) or not SERVICE_WHITELIST:
                    lstServices.append(nagServ)
            
            host.clearSeries()
            for service in lstServices:
                
                stateError = True
                if (service["state"] == 0): stateError = False

                self.DynaConn.checkIsEvent(host.displayName, service["description"], stateError)

                lstMetricas = self.NagiosConn.parsePerfData(service["perf_data"])
                
                for metrica in lstMetricas:
                    host.addSerie(service["description"], metrica, lstMetricas[metrica][0])
    
    def EnviarMetricas(self):
        '''Eviar los datos a Dynatrace'''
        self.DynaConn.sendMetrics()

    def EnviarEventos(self):
        '''Eviar los eventos a Dynatrace'''
        self.DynaConn.sendEvents()

#####MAIN###############################################################################################################
oInteg = Integracion()
s = sched.scheduler(time.time, time.sleep)

def programa(start, end, interval, func, args=()):
    event_time = start
    while event_time < end:
        s.enterabs(event_time, 0, func, args)
        event_time += interval

    s.run()

def service_integration():
    oInteg.CargarMetricas()
    oInteg.EnviarMetricas()
    oInteg.EnviarEventos()

def main():
    try:
        oInteg.CargarHosts()

        print("Inicio - Recoleccion de Metricas de Nagios")

        #Ajustar los tiempos (+100000 1 dia)
        programa(time.time()+5, time.time()+100000, 90, service_integration)

    except IntegrationErrors.NagiosToDynaError as err:
        print(err)

if __name__ == '__main__':
    main()