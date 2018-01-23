import logging
import struct
import copy
import networkx as nx
from datetime import datetime
import time
from dateutil import relativedelta

from operator import attrgetter
from ryu import cfg
from ryu.base import app_manager
from ryu.controller import ofp_event
from ryu.controller.handler import MAIN_DISPATCHER, DEAD_DISPATCHER
from ryu.controller.handler import CONFIG_DISPATCHER
from ryu.controller.handler import set_ev_cls
from ryu.ofproto import ofproto_v1_3
from ryu.lib.packet import packet
from ryu.lib.packet import ethernet
from ryu.lib.packet import ipv4
from ryu.lib.packet import arp
from ryu.lib import hub

from ryu.topology import event, switches
from ryu.topology.api import get_switch, get_link
import setting
import threading

import network_monitor
import network_execute
import network_knowledge

CONF = cfg.CONF


class NetworkPlan(app_manager.RyuApp):
    """
        NetworkAwareness is a Ryu app for plan actions that will be done.
        Questa app fornisce un elenco di azioni da intraprendere nel caso in cui
        l'analizzatore dovesse rilevare traffico sospetto.
    """
    OFP_VERSIONS = [ofproto_v1_3.OFP_VERSION]

    def __init__(self, *args, **kwargs):
        super(NetworkPlan, self).__init__(*args, **kwargs)
        self.name = 'plan'
        #self.sem_plan = threading.Semaphore(0)
        #self.sem_plan2 = threading.Semaphore(1)
        self.plan_thread = hub.spawn(self._plan)
        print("Plan thread: ", self.plan_thread)
    

    def _plan(self):
        print "PLAN PARTITO"

        while (1):

            print ('sem_plan.acquire()')
            network_knowledge.nk.sem_plan.acquire()
            print ('fatto')
            
            #m = network_knowledge.nk.dict_speed.items()
            x = network_knowledge.nk.dict_avg.items()   #Returns a list of dict's (key, value) tuple pairs 
            print network_knowledge.nk.dict_speed
            st = self.somma(network_knowledge.nk.dict_speed)            

            print ('sem_mon.release()')
            network_knowledge.nk.sem_mon.release()
            print ('fatto')


            if (st < setting.SRV_THRSH):    #SRV_THRSH = 2621440 = 20 Mbit
                print ("Entrato nel st < setting.SRV_THRSH" + str(st))                
                hub.sleep(1)

            if (st >= setting.SRV_THRSH):
                
                print ('sem_plan2.acquire()')
                network_knowledge.nk.sem_plan2.acquire()
                print ('fatto')

                print ("Entrato nel st >= setting.SRV_THRSH" + str(st))                
                #m = network_knowledge.nk.dict_speed.items()
                print('%%%' + str(x))
                
                for k, v in x:
                    if (v>2*setting.MAX_SPEED):     #x>10mbps

                        t = network_knowledge.nk.dict_flow_ts.get(k, 0)   #ricava il timestamp necessario per modificare la blacklist
                        network_knowledge.nk.edit_blacklist(k, t) #passa ip e ts, inserisci  l host nella blacklist
                        
                        '''
                        creazione dizionario con parametri necessari al modulo network_execute
                        datapath[2], src_ip[3], dst_ip n[4], in_port n[5]
                        '''
                        exe_action = 'block'
                        exe_src = k
                        exe_dpid = network_knowledge.nk.dict_dpid.get(k, 0)
                        exe_dst = '10.0.0.1'    #serve all execute, anche se sappiamo gia il nostro obiettivo dell attacco
                        exe_port = network_knowledge.nk.dict_in_port.get(k, 0)
                        exe_flow_ts = t
                        
                        network_knowledge.nk.add_exe_entry(k, exe_action, exe_src, exe_dpid, exe_dst, exe_port, exe_flow_ts)               


                    elif (v>setting.MAX_SPEED and v<2*setting.MAX_SPEED):   #ossia 5mbps<x<10mbps

                        diff = 0
                        r = network_knowledge.nk.get_blocked_source(k)   #invio richiesta di check dell ip_src e mi riestituisce flow_ts
                        if (r == False):
                            pass
                        else:
                            now_ts = datetime.now()                        
                            diff = (now_ts-r).total_seconds()   #differenza tra now_ts e flow_ts

                            print('<><><><><> differenza    ' + str(diff))
                            print('<><><><> now_ts    ' + str(now_ts)) 
                            print('<><><> flow_ts    ' + str(r))
                            print('<><><>' + str(network_knowledge.nk.blocked_sources))
                        
                        if (diff == False or diff <=10):    #se non presente nella blacklist o <20sec fa niente
                            
                            t = network_knowledge.nk.dict_flow_ts.get(k, 0)           
                            '''
                            creazione dizionario con parametri necessari al modulo network_execute
                            datapath[2], src_ip[3], dst_ip n[4], in_port n[5]
                            '''
                            exe_action = 'limit1'
                            exe_src = k
                            exe_dpid = network_knowledge.nk.dict_dpid.get(k, 0)
                            exe_dst = '10.0.0.1'
                            exe_port = network_knowledge.nk.dict_in_port.get(k, 0)
                            exe_flow_ts = t
                            
                            network_knowledge.nk.add_exe_entry(k, exe_action, exe_src, exe_dpid, exe_dst, exe_port, exe_flow_ts)
                            

                        elif (diff > 10):   #se presente nella blacklist da almeno 20 secondi
                            
                            t = network_knowledge.nk.dict_flow_ts.get(k, 0)
                            '''
                            creazione dizionario con parametri necessari al modulo network_execute
                            datapath[2], src_ip[3], dst_ip n[4], in_port n[5]
                            '''
                            exe_action = 'limit2'
                            exe_src = k
                            exe_dpid = network_knowledge.nk.dict_dpid.get(k, 0)
                            exe_dst = '10.0.0.1'
                            exe_port = network_knowledge.nk.dict_in_port.get(k, 0)
                            exe_flow_ts = t
                            
                            network_knowledge.nk.add_exe_entry(k, exe_action, exe_src, exe_dpid, exe_dst, exe_port, exe_flow_ts)
                            
                print ('sem_exec.release()')
                network_knowledge.nk.sem_mon.release()
                network_knowledge.nk.sem_exec.release()
                print ('fatto')

    def somma(self, a):
        sum_thrsh = 0
        sum_thrsh = sum( [val[0] for val in a.values()] )
        print a
        return sum_thrsh 
    '''
    def findMaxValue (self, b): #riceve lista con tuple [(ip, 5val),(ip2, 5val)...]
        c = max(b.iteritems(), key=operator.itemgetter(1))[0]
        return c    #ritorna solo ip
    '''
    #hub.sleep(5)