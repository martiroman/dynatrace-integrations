'''
Dynatrace API

Envia a Dynatrace:
+ CustomHosts
+ Metrics
+ Events
'''

from xml.sax.handler import EntityResolver
import requests
import time
import datetime
import json

##Clases Dynatrace
class DataPoint(object):
    def __init__(self, tiempo, valor):
        self.timestamp = int(time.mktime(tiempo.timetuple()) * 1000)
        self.valor = valor

    #TODO: Si no es valor numerico
    def formatDataPoint(self):
        return [self.timestamp, float(self.valor)]

class Serie(object):
    def __init__(self, ServiceName, dimensions):
        self.timeseriesId = 'custom:host.service.' + ServiceName.replace(" ", "").lower()
        self.dimensions = { 'metrica' : dimensions }
        self.dataPoints = []
    
    def addDataPoint(self, tiempo, valor):
        dp = DataPoint(tiempo, valor)
        self.dataPoints.append(dp.formatDataPoint())

class Event(object):
    def __init__(self, eventType, title, entitySelector):
        self.eventType = eventType
        self.title = title
        #Si es null toma la hora actual
        #self.startTime = startTime
        #self.endTime = endTime
        #The timeout will automatically be capped to a maximum of 300 minutes (5 hours). Problem-opening events can be refreshed and therefore kept open by sending the same payload again. 
        self.timeout = 300
        self.entitySelector = entitySelector
        self.properties = {
            "dt.event.allow_davis_merge" : "false",
        }

    def setProperty(self, nombre, valor):
        self.properties["'" + nombre + "'"] = valor

    def toJson(self):
        return json.dumps(self, default=lambda o: o.__dict__, 
            sort_keys=True, indent=4)
        
# "hostNames": [ "coffee-machine.dynatrace.internal.com" ]                        
class CustomHost(object):
    def __init__(self, displayName, ipAddresses, listenPorts, type, favicon, configUrl, grupo):
        self.displayName = displayName
        self.ipAddresses = [ipAddresses]
        self.listenPorts = listenPorts
        self.type = type
        self.favicon = favicon
        self.configUrl = configUrl
        self.series = []
        self.tags = []
        self.group = grupo
        #self.properties = { 'ip' : ipAddresses }

    def addSerie(self, servicename, metrica, valor):
        dt = datetime.datetime.now()
        serie = Serie(servicename, metrica)
        serie.addDataPoint(dt, valor)
        self.series.append(serie)

    def addTag(self, value):
        self.tags = value

    def clearSeries(self):
        self.series = []

    def toJson(self):
        return json.dumps(self, default=lambda o: o.__dict__)

class Connection(object):
    def __init__(self, api_url, api_token):
        self.api_url = api_url
        self.api_token = api_token
        self.lstHosts = []
        self.lstEvents = []

    def addCustomHost(self, name, address, puerto, type, favicon, configUrl, grupo):
        dHost = CustomHost(name, address, puerto, type, favicon, configUrl, grupo)
        self.lstHosts.append(dHost)
        return dHost
    
    def getHosts(self):
        return self.lstHosts

    def addEvent(self, eventType, title, entitySelector, properties = {}): 

        dEvent = Event(eventType, title, entitySelector)
        
        if properties: dEvent.properties.update(properties)
        
        self.lstEvents.append(dEvent)
        return dEvent

    def getEvents(self):
        return self.lstEvents

    def sendMetrics(self):
        for host in self.lstHosts:
            r = requests.post(self.api_url + '/api/v1/entity/infrastructure/custom/' + host.displayName + '?Api-Token=' + self.api_token, json=json.loads(host.toJson()))
            print("\n PAYLOAD: ")
            print(json.loads(host.toJson()))
            print(host.displayName +": " + r.text + " | " + r.reason)

    def sendEvents(self):
        for event in self.lstEvents:
            r = requests.post(self.api_url + '/api/v2/events/ingest?Api-Token=' + self.api_token, json=json.loads(event.toJson()))
            print("\n PAYLOAD: ") 
            print(json.loads(event.toJson()))
            print(event.entitySelector + " | " + event.title + " | " + r.text)

    def searchDynaHost(self, ipAddress):
        r = requests.get(self.api_url + '/api/v2/entities/?entitySelector=TYPE%28HOST%29%2C%20ipAddress%28' + ipAddress + '%29&Api-Token=' + self.api_token)
        return json.loads(r.text)

    def emptyCache(self):
        self.lstHosts = []
        self.lstEvents = []

    def createMetric():
        #TODO: Crear metrica en Dyna
        '''Pendiente'''

    def checkIsEvent(self, hostName, serviceName, errorState, properties = {}):
        encontrado = False

        entitySelector = self.getEntitySelector(hostName) 

        for event in self.lstEvents:
            if event.title == serviceName and event.entitySelector == entitySelector:
                encontrado = True

        if encontrado == True:
            #TODO: Si el evento tiene ACK enviar el Cierre a Dynatrace  
            if not errorState:
                print("eliminar evento")
        else:
            if errorState:   
                #Si el evento tiene ACK enviar el Cierre a Dynatrace              
                self.addEvent("CUSTOM_ALERT", serviceName, entitySelector, properties)

    def getEntitySelector(self, hostName):
        dHost = False
        for dHost in self.lstHosts:
            if dHost.displayName == hostName:
                break
        
        busqueda = hostName
        if dHost:
            busqueda = dHost.ipAddresses[0]

        entityType = "CUSTOM_DEVICE" 
        if self.searchDynaHost(busqueda)["totalCount"] > 0:
            entityType = "HOST" 
        
        entitySelector = "type(" + entityType + "),ipAddress(" + busqueda + ")"
        
        return entitySelector