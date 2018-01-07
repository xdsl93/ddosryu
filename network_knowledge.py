import logging
from logging import LoggerAdapter

import struct
import copy
import networkx as nx
from operator import attrgetter
from ryu import cfg
from ryu.base import app_manager
from ryu.controller import ofp_event
from ryu.controller.handler import MAIN_DISPATCHER, DEAD_DISPATCHER
from ryu.controller.handler import CONFIG_DISPATCHER, HANDSHAKE_DISPATCHER
from ryu.controller.handler import set_ev_cls
from ryu.ofproto import ofproto_v1_3_parser
from ryu.ofproto import ofproto_v1_3
from ryu.lib.dpid import str_to_dpid
from ryu.lib.packet import packet
from ryu.lib.packet import ethernet
from ryu.lib.packet import ipv4
from ryu.lib.packet import arp
from ryu.lib import hub
from ryu.lib import lacplib
from ryu import utils
from threading import Timer
import dpkt

from ryu.topology import event, switches
from ryu.topology.api import get_switch, get_link
import setting
import threading

CONF = cfg.CONF


class NetworkKnowledge(app_manager.RyuApp):
    """
        Il modulo knowledge contiene la conoscienza, i moduli PLAN ed EXECUTE
        ricavano e aggiornano le informazioni dei flussi nella knowledge
    """
    OFP_VERSIONS = [ofproto_v1_3.OFP_VERSION]

    def __init__(self, *args, **kwargs):
        super(NetworkKnowledge, self).__init__(*args, **kwargs)
        self.name = 'knowledge'
        self.blocked_sources = {}
        self.dict_avg = {}
        self.dict_speed = {}
        self.dict_dpid = {}
        self.dict_in_port = {}
        self.dict_flow_ts = {}
        self.dict_action = {}

        self.sem_mon = threading.Semaphore(100)
        
        self.sem_plan = threading.Semaphore(0)
        self.sem_plan2 = threading.Semaphore(1)

        self.sem_exec = threading.Semaphore(0)
        
    
    def edit_blacklist(self, ip_src, ts):
        '''
        if ip_src is not a key, set it as key and create an empty list as value
        and after append 'ts' to it

        # setdefault is that it initializes the value for that key if that key 
        # is not defined, otherwise it does nothing. 

        Example:
        >>>a
        {'somekey': [1, 2]}
        '''
        if not ip_src in self.blocked_sources:              #hash table dei dict piu efficente rispetto ricerca lineare di un vettore
            self.blocked_sources.setdefault(ip_src, [])     
            self.blocked_sources[ip_src].append(ts)
        else:
            self.blocked_sources[ip_src].append(ts)



    '''
    TO-DO
    come fare a chiamare il primo valore dell array dei valori per cancellarlo?
    del(self.blocked_sources["ip_src"][0])  dovrebbe fare questo lavoro, ma lo deve cancellare solo se il metodo
    del plan vede che l'ip e' presente nella blacklist da almeno 10 secondi, get_blocked_sources lo cancella
    ad ogni chiamata
    '''
    def get_blocked_source(self, ip_src):
        if not ip_src in self.blocked_sources:
            return False
        elif ip_src in self.blocked_sources:
            timestamp = self.blocked_sources[ip_src][0]     #primo valore array
            return timestamp                                
                
        #guarda TO-DO
    
    
    '''
    add_speed crea dizionario con
    key: ip_src
    value: fs
    e successivamente se host non presente nel dizionario
    aggiunge i rispettivi parametri negli altri dizionari
    '''
    def add_speed(self, ip_src, dpid, in_port, flow_ts, fs):
        if not ip_src in self.dict_speed:
            self.dict_speed.setdefault(ip_src, []) 
            self.dict_speed[ip_src] = fs

            self.add_dpid(ip_src, dpid)
            self.add_in_port(ip_src, in_port)
            self.add_flow_ts(ip_src, flow_ts)
            print ("Aggiunto HOST   " + str(self.dict_speed))

        else:
            self.dict_speed[ip_src] = fs
            print ("Update HOST     " + str(self.dict_speed))            
    

    def add_dpid(self, ip_src, dpid):
        if not ip_src in self.dict_dpid:
            self.dict_dpid.setdefault(ip_src, None) 
            self.dict_dpid[ip_src] = dpid
            print ("Aggiunta DPID   " + str(self.dict_dpid))

    def add_in_port(self, ip_src, in_port):
        if not ip_src in self.dict_in_port:
            self.dict_in_port.setdefault(ip_src, None) 
            self.dict_in_port[ip_src] = in_port
            print ("Aggiunta IN_PORT" + str(self.dict_in_port))

    def add_flow_ts(self, ip_src, flow_ts):
        if not ip_src in self.dict_flow_ts:
            self.dict_flow_ts.setdefault(ip_src, None) 
            self.dict_flow_ts[ip_src] = flow_ts
            print ("Aggiunta FLOW_TS" + str(self.dict_flow_ts))

    def add_exe_entry(self, ip_src, exe_action, exe_src, exe_dpid, exe_dst, exe_port, exe_flow_ts):
        if not ip_src in self.dict_action:
            v = [exe_action, exe_src, exe_dpid, exe_dst, exe_port, exe_flow_ts]
            self.dict_action.setdefault(ip_src, []) 
            self.dict_action[ip_src] = v
            print ("entry EXECUTE" + str(self.dict_action))
        else: 
            pass
    
    def del_exe_entry(self, ip_src):
        del dict_action[ip_src]

    def get_dict_speed(self):
        return self.dict_speed
    '''
    add_host_to_dict crea dizionario con
    key: ip_src
    value: [fs, self.datapaths[dpid], stat.match['ipv4_src'], stat.match['ipv4_dst'], stat.match['in_port'], flow_ts]
    '''
    
    '''
    def add_host_to_dict(self, ip_src, val):        #ip_src --> key, mega array --> value
        if not ip_src in self.dict_connected_hosts:              
            self.dict_connected_hosts.setdefault(ip_src, []) 
            self.dict_connected_hosts[ip_src] = val     #replace with new message_flow
    
            #self.dict_connected_hosts[ip_src].append(val)
            print ("+++++++" + str(self.dict_connected_hosts))
        else:
            self.dict_connected_hosts[ip_src] = val     #replace with new message_flow
            print ("-------" + str(self.dict_connected_hosts))
    '''
    '''
    def add_host_to_dict(self, ip_src, dpid, in_port, flow_ts, fs):
        if not ip_src in self.dict_connected_hosts:
            self.dict_connected_hosts[ip_src] = {}
            self.dict_connected_hosts[ip_src][dpid] = {}
            self.dict_connected_hosts[ip_src][dpid][in_port] = {}
            self.dict_connected_hosts[ip_src][dpid][in_port][flow_ts] = []
            self.dict_connected_hosts[ip_src][dpid][in_port][flow_ts] = fs
            print ("+++++++" + str(self.dict_connected_hosts))

        if ip_src in self.dict_connected_hosts:
        
            
            self.dict_connected_hosts[ip_src][dpid][in_port][flow_ts] = fs
            print ("-------" + str(self.dict_connected_hosts))

    '''



nk=NetworkKnowledge()
