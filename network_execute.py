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
import dpkt

from ryu.topology import event, switches
from ryu.topology.api import get_switch, get_link
import setting
import threading

import network_monitor
import network_topo_disc
import network_plan
import network_knowledge

CONF = cfg.CONF


class NetworkExecute(app_manager.RyuApp):
    """
        Il modulo execute riceve i parametri dal plan ed esegue le operazioni sui flussi,
        in base alle decisioni intraprese dal plan. Consuma la coda action_queue e poi una 
        volta eseguita l'operazione la elimina
    """
    OFP_VERSIONS = [ofproto_v1_3.OFP_VERSION]

    def __init__(self, *args, **kwargs):
        super(NetworkExecute, self).__init__(*args, **kwargs)
        self.name = 'execute'

        #self.sem_exec = threading.Semaphore(0)
        self.execute_thread = hub.spawn(self._execute)
        print("Execute thread: ", self.execute_thread)

    def _execute(self):
        print "EXECUTE PARTITO"

        while (1):
            
            print ('sem_exec.acquire()')
            network_knowledge.nk.sem_exec.acquire()
            print ('fatto')
            print "EXECUTE PARTITO"
            
            n = network_knowledge.nk.dict_action.items()
            #if (network_knowledge.nk.dict_action.has_key(n[3])): 
            #    network_knowledge.nk.del_exe_entry(n[3])    #cancella host nel dizionario delle azioni in sospeso
            #dict.get(key, default=None)
            print n
            for k, v in n:
                if (v[0] == "block"):
                    #print str(n)
                    self.drop_flow(v[2], v[1], v[3], v[4]) #passa datapath[2], src_ip[1], dst_ip v[3], in_port v[4]
                    print v[3]
                elif (v[0] == "limit1"):
                    #print("$$$" + str(n))       
                    self.limit_flow1(v[2], v[1], v[3], v[4]) 
                    network_knowledge.nk.edit_blacklist(v[1], v[5]) #passa src_ip e flow_ts
                elif (v[0] == "limit2"):
                    self.limit_flow2(v[2], v[1], v[3], v[4])
                else:
                    return

            print ('sem_plan2.release()')
            network_knowledge.nk.sem_plan2.release()
            print ('sem_plan2.release()')

    
    '''
    il metodo blocca il flusso riguardante i dati passati
    '''
    def drop_flow(self, dp, ip_src, ip_dst, in_port):
        datapath = dp 
        ofproto = datapath.ofproto
        parser = datapath.ofproto_parser

        match = parser.OFPMatch(eth_type=0x0800,
                                ipv4_src=ip_src, 
                                ipv4_dst=ip_dst,
                                in_port=in_port)
        inst = [parser.OFPInstructionActions(ofproto.OFPIT_CLEAR_ACTIONS, [])]
        mod = parser.OFPFlowMod(datapath=datapath,
                                command=ofproto.OFPFC_ADD,
                                match=match, instructions=inst)  #instruction=[] droppa il flusso 
        print "deleting flow entries in the table "
        datapath.send_msg(mod)


    #handler messaggio errore se flusso non riesce ad essere modificato
    @set_ev_cls(ofp_event.EventOFPErrorMsg,
            [HANDSHAKE_DISPATCHER, CONFIG_DISPATCHER, MAIN_DISPATCHER])
    def error_msg_handler(self, ev):
        msg = ev.msg

        self.logger.debug('OFPErrorMsg received: type=0x%02x code=0x%02x ' 
                        'message=%s',
                        msg.type, msg.code, utils.hex_array(msg.data))


    '''
    il metodo limita la velocita del flusso
    a 100kbps per 10 secondi, po riprende alla velocita originaria
    
    TO-DO: salvare nella blacklist ip host in causa e la volta successiva
    che viene individuato uno sforamento limitarlo ancora di piu o bloccarlo
    '''
    # la prima parte imposta il meter_id=1, volendo si possono impostarne anche altri

    def limit_flow1(self, dp, ip_src, ip_dst, in_port):
        datapath = dp
        ofproto = datapath.ofproto
        parser = datapath.ofproto_parser
        
        #primo meter
        bands = [parser.OFPMeterBandDrop(type_=ofproto.OFPMBT_DROP, len_=0, rate=100, burst_size=10)]

        req=parser.OFPMeterMod(datapath=datapath,
                            command=ofproto.OFPMC_ADD,
                            flags=ofproto.OFPMF_KBPS,
                            meter_id=3,
                            bands=bands)
        datapath.send_msg(req)

        #applica meter_id=3 al flusso interessato
        match = parser.OFPMatch(eth_type=0x0800,
                                ipv4_src=ip_src, 
                                ipv4_dst=ip_dst,
                                in_port=in_port)
        
        actions = [parser.OFPActionOutput(port=ofproto.OFPP_CONTROLLER)]
        inst = [parser.OFPInstructionActions(ofproto.OFPIT_APPLY_ACTIONS, actions), 
                parser.OFPInstructionMeter(3,ofproto.OFPIT_METER)]

        mod = parser.OFPFlowMod(datapath=datapath, 
                                match=match, cookie=0,
                                command=ofproto.OFPFC_ADD, 
                                idle_timeout=0,    #0 o 10 non cambia nulla
                                hard_timeout=20,    #durata limitazione 10 secondi
                                priority=3,
                                instructions=inst)
        

        
        print "limit flow entries in the table "
        datapath.send_msg(mod)

            
    '''
    Se host attaccante non riduce il suo output, quando il primo meter termina
    viene eseguito questo secondo meter piu restrittivo
    '''
    def limit_flow2(self, dp, ip_src, ip_dst, in_port):
        datapath = dp
        ofproto = datapath.ofproto
        parser = datapath.ofproto_parser
        
        #secondo meter
        bands = [parser.OFPMeterBandDrop(type_=ofproto.OFPMBT_DROP, len_=0, rate=50, burst_size=10)]

        req=parser.OFPMeterMod(datapath=datapath,
                            command=ofproto.OFPMC_ADD,
                            flags=ofproto.OFPMF_KBPS,
                            meter_id=4,
                            bands=bands)
        datapath.send_msg(req)

        #applica meter_id=4 al flusso interessato

        match = parser.OFPMatch(eth_type=0x0800,
                                ipv4_src=ip_src, 
                                ipv4_dst=ip_dst,
                                in_port=in_port)

        actions = [parser.OFPActionOutput(port=ofproto.OFPP_CONTROLLER)]
        inst = [parser.OFPInstructionActions(ofproto.OFPIT_APPLY_ACTIONS, actions), 
                parser.OFPInstructionMeter(4,ofproto.OFPIT_METER)]
        mod = parser.OFPFlowMod(datapath=datapath, 
                            match=match, cookie=0,
                            command=ofproto.OFPFC_ADD, 
                            idle_timeout=0,
                            hard_timeout=50,
                            priority=3,
                            instructions=inst)
        print "limit for second time flow entries in the table"
        datapath.send_msg(mod)

    '''    
    Ascoltatore che da in output solo le statistiche del meter configurato
    '''
    @set_ev_cls(ofp_event.EventOFPMeterConfigStatsReply, MAIN_DISPATCHER)
    def meter_config_stats_reply_handler(self, ev):
        configs = []
        for stat in ev.msg.body:
            configs.append('length=%d flags=0x%04x meter_id=0x%08x '
                            'bands=%s' %
                            (stat.length, stat.flags, stat.meter_id, stat.bands))
        self.logger.debug('MeterConfigStats: %s', configs)