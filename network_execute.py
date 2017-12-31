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

        self.sem_exec = threading.Semaphore(0)
        self.execute_thread = hub.spawn(self._execute)
        print("Execute thread: ", self.execute_thread)

    def _execute(self):
        print "EXECUTE PARTITO"

        
        while (1):
            
            print ('sem_exec.acquire()')
            self.sem_exec.acquire()
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
                    self.limit_flow1(v[2], v[1], v[3], v[4]) #passa datapath[2], src_ip[3], dst_ip v[4], in_port v[5]
                    network_knowledge.nk.edit_blacklist(v[1], v[5]) #passa src_ip e flow_ts
                elif (v[0] == "limit2"):
                    self.limit_flow2(v[2], v[1], v[3], v[4])
                else:
                    return

            print ('sem_plan2.release()')
            network_plan.p.sem_plan2.release()
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
        #inst = [] 
        #actions = [parser.OFPActionOutput(ofproto.OFPP_NORMAL, 0)]
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
        datapath = dp ##
        ofproto = datapath.ofproto
        parser = datapath.ofproto_parser

        #self.ipv4_src = ip_src
        
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
                            command=ofproto.OFPMC_ADD,  # o MODIFY?...non cambia nulla
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
    









    '''        
    def _execute(self):
        while (1):
            
            self.exec_sem.release()
            n = coda_azione.aq.pop()
            #print n
            if (n[0] == "block"):
                #print str(n)
                self.drop_flow(n[2], n[3], n[4], n[5]) #passa datapath[2], src_ip[3], dst_ip n[4], in_port n[5]
                print n[3]
            elif (n[0] == "limit1"):
                #print("$$$" + str(n))       
                    self.limit_flow1(n[2], n[3], n[4], n[5]) #passa datapath[2], src_ip[3], dst_ip n[4], in_port n[5]
                    network_knowledge.nk.edit_blacklist(n[3], n[6]) #passa src_ip e flow_ts
            elif (n[0] == "limit2"):
                    self.limit_flow2(n[2], n[3], n[4], n[5])
            else:
                return
            self.exec_sem.acquire()
    '''


    '''
    def limit_flow(self, dp, ip_src, ip_dst, in_port):
        datapath = dp ##
        ofproto = datapath.ofproto
        parser = datapath.ofproto_parser

        # install table-miss flow entry
        match = parser.OFPMatch(eth_type=0x0800,
                                ipv4_src=ip_src, 
                                ipv4_dst=ip_dst,
                                in_port=in_port)

        actions = [parser.OFPActionOutput(ofproto.OFPP_CONTROLLER, ofproto.OFPCML_NO_BUFFER)]
        rate=100
        burst_size=0
        bands=[]
        bands.append(parser.OFPMeterBandDrop(rate, burst_size))
        meter_mod = parser.OFPMeterMod(datapath=datapath,  ##
                                       command=ofproto.OFPMC_ADD,
                                       flags=ofproto.OFPMF_KBPS,                                       
                                       meter_id=1, 
                                       bands=bands)
        datapath.send_msg(meter_mod)

        # Add the meter to the table miss
        inst = [parser.OFPInstructionActions(ofproto.OFPIT_APPLY_ACTIONS, actions), 
                                             parser.OFPInstructionMeter(1)]
        mod = parser.OFPFlowMod(datapath=datapath, 
                                priority=0,
                                match=match, 
                                instructions=inst)
        print "limit flow entries in the table "
        datapath.send_msg(mod)
    '''
    



    '''
    @set_ev_cls(ofp_event.EventOFPPacketIn, MAIN_DISPATCHER)
    def _packet_in_handler(self, ev):
        msg = ev.msg
        datapath = msg.datapath
        ofproto = datapath.ofproto
        parser = datapath.ofproto_parser
        in_port = msg.match['in_port']

        pkt = packet.Packet(msg.data)
        eth = pkt.get_protocols(ethernet.ethernet)[0]

        dst = eth.dst
        src = eth.src

        dpid = datapath.id
        self.mac_to_port.setdefault(dpid, {})

        self.logger.info("packet in %s %s %s %s", dpid, src, dst, in_port)
        
        # learn a mac address to avoid FLOOD next time.
        self.mac_to_port[dpid][src] = in_port

        if dst in self.mac_to_port[dpid]:
            out_port = self.mac_to_port[dpid][dst]
        else:
            out_port = ofproto.OFPP_FLOOD

        actions = [parser.OFPActionOutput(out_port)]

        # install a flow to avoid packet_in next time
        if out_port != ofproto.OFPP_FLOOD:
            match = parser.OFPMatch(in_port=in_port, eth_dst=dst)
            self.add_flow(datapath, 1, match, actions)
        data = None
        if msg.buffer_id == ofproto.OFP_NO_BUFFER:
            data = msg.data
        print('FLUSSO BLOCCATO')
    

    def add_flow(self, dp, p, match, actions, idle_timeout=0, hard_timeout=0):
        ofproto = dp.ofproto
        parser = dp.ofproto_parser

        inst = [parser.OFPInstructionActions(ofproto.OFPIT_APPLY_ACTIONS,
                                             actions)]

        mod = parser.OFPFlowMod(datapath=dp, priority=p,
                                idle_timeout=idle_timeout,
                                hard_timeout=hard_timeout,
                                match=match, instructions=inst)
        dp.send_msg(mod)
    '''




    '''
    def del_flow(self, datapath):
        ofp = datapath.ofproto
        ofp_parser = datapath.ofproto_parser

        cookie = cookie_mask = 0
        table_id = 0
        idle_timeout = hard_timeout = 0
        priority = 32768
        buffer_id = ofp.OFP_NO_BUFFER
        match = ofp_parser.OFPMatch(in_port=1, eth_dst='ff:ff:ff:ff:ff:ff')
        actions = [ofp_parser.OFPActionOutput(ofp.OFPP_NORMAL, 0)]
        inst = [ofp_parser.OFPInstructionActions(ofp.OFPIT_APPLY_ACTIONS,
                                                actions)]
        req = ofp_parser.OFPFlowMod(datapath, cookie, cookie_mask,
                                    table_id, ofp.OFPFC_DELETE,
                                    idle_timeout, hard_timeout,
                                    priority, buffer_id,
                                    ofp.OFPP_ANY, ofp.OFPG_ANY,
                                    ofp.OFPFF_SEND_FLOW_REM,
                                    match, inst)
        datapath.send_msg(req)
    '''

    '''
    def del_flow(self, datapath):
        self.logger.debug('send stats request: %016x', datapath.id)
        ofproto = datapath.ofproto
        parser = datapath.ofproto_parser

        req = parser.OFPFlowStatsRequest(datapath)
        datapath.send_msg(req)

        req = parser.OFPPortStatsRequest(datapath, 0, ofproto.OFPP_ANY)
        datapath.send_msg(req)

    @set_ev_cls(ofp_event.EventOFPFlowStatsReply, MAIN_DISPATCHER)
    def _flow_stats_reply_handler(self, ev):
        body = ev.msg.body
        for stat in sorted([flow for flow in body if flow.priority >= 1],
                                key=lambda flow: (flow.instructions[0].actions[0])):
		#add a flow to drop the packet
		dp = ev.msg.datapath
		ofp = dp.ofproto
		parser = dp.ofproto_parser

		match = parser.OFPMatch(in_port=stat.match['in_port'])
		actions = [parser.OFPActionSetQueue(1)]
		inst = [parser.OFPInstructionActions(ofp.OFPIT_APPLY_ACTIONS,actions),parser.OFPInstructionGotoTable(1)]
		mod = parser.OFPFlowMod(datapath=dp, priority=1,match=match, instructions=inst)
		dp.send_msg(mod)
    '''
  





    '''
    @set_ev_cls(ofp_event.EventOFPPacketIn, MAIN_DISPATCHER)
    def _packet_in_handler(self, ev):
        msg = ev.msg
        datapath = msg.datapath
        ofproto = datapath.ofproto

        pkt = packet.Packet(msg.data)
        eth = pkt.get_protocol(ethernet.ethernet)


        dst = eth.dst
        src = eth.src

        dpid = datapath.id
        self.mac_to_port.setdefault(dpid, {})

        self.logger.info("packet in %s %s %s %s", dpid, src, dst, msg.in_port)

        # learn a mac address to avoid FLOOD next time.
        self.mac_to_port[dpid][src] = msg.in_port

        if dst in self.mac_to_port[dpid]:
            out_port = self.mac_to_port[dpid][dst]
        else:
            out_port = ofproto.OFPP_FLOOD

        actions = [datapath.ofproto_parser.OFPActionOutput(out_port)]

        # install a flow to avoid packet_in next time
        if out_port != ofproto.OFPP_FLOOD:
            self.add_flow(datapath, msg.in_port, dst, actions)

        data = None
        if msg.buffer_id == ofproto.OFP_NO_BUFFER:
            data = msg.data

        out = datapath.ofproto_parser.OFPPacketOut(
            datapath=datapath, buffer_id=msg.buffer_id, in_port=msg.in_port,
            actions=actions, data=data)
        datapath.send_msg(out)
    '''







    '''
    #cancellazione diretta del flusso
   
    def delete_flow(self, datapath):
        ofproto = datapath.ofproto
        parser = datapath.ofproto_parser
        for dst in self.mac_to_port[datapath.id].keys():
            match = parser.OFPMatch(eth_dst=dst)
            mod = parser.OFPFlowMod(
                datapath, command=ofproto.OFPFC_DELETE,
                out_port=ofproto.OFPP_ANY, out_group=ofproto.OFPG_ANY,
                priority=1, match=match)
        datapath.send_msg(mod)
    '''

    '''
    #blocco del flusso senza bloccare host 
    
    def create_blocking_flow(self, ip_src):
        # This should be reset when the flow has timed out
        if not ip_src in self.blocked_sources:
            self.blocked_sources.append(ip_src)
            match = datapath.ofproto_parser.OFPMatch(dl_type=0x0800, nw_src=ipv4_text_to_int(ip_src), nw_src_mask=32)
            mod = datapath.ofproto_parser.OFPFlowMod(
                datapath=datapath, match=match, cookie=random_int(),
                command=datapath.ofproto.OFPFC_ADD, idle_timeout=10, hard_timeout=0,
                priority=0x8000, flags=datapath.ofproto.OFPFF_SEND_FLOW_REM)
            datapath.send_msg(mod)
            print 'creating blocking flow for source: {0}'.format(ip_src)
    '''


    '''
    def blocca(self, datapath):
        ofp = datapath.ofproto
        ofp_parser = datapath.ofproto_parser

        cookie = cookie_mask = 0
        table_id = 0
        idle_timeout = hard_timeout = 0
        priority = 32768
        buffer_id = ofp.OFP_NO_BUFFER
        importance = 0
        match = ofp_parser.OFPMatch(in_port=1, eth_dst='ff:ff:ff:ff:ff:ff')
        actions = [ofp_parser.OFPActionOutput(ofp.OFPP_NORMAL, 0)]
        inst = [ofp_parser.OFPInstructionActions(ofp.OFPIT_APPLY_ACTIONS,
                                                actions)]
        req = ofp_parser.OFPFlowMod(datapath, cookie, cookie_mask,
                                    table_id, ofp.OFPFC_ADD,
                                    idle_timeout, hard_timeout,
                                    priority, buffer_id,
                                    ofp.OFPP_ANY, ofp.OFPG_ANY,
                                    ofp.OFPFF_SEND_FLOW_REM,
                                    importance,
                                    match, inst)
        datapath.send_msg(req)
    '''


    '''
    il metodo limita la velocita del flusso
    a 100kbps
    '''
    '''
    # la prima parte imposta il meter_id=1, volendo si possono impostarne anche altri

    def limit_flow(self, dp, ip_src, ip_dst, in_port):
        datapath = dp ##
        ofproto = datapath.ofproto
        parser = datapath.ofproto_parser

        bands = [parser.OFPMeterBandDrop(type_=ofproto.OFPMBT_DROP, len_=0, rate=100, burst_size=10)]

        req=parser.OFPMeterMod(datapath=datapath,
                               command=ofproto.OFPMC_ADD,
                               flags=ofproto.OFPMF_KBPS,
                               meter_id=3,
                               bands=bands)

        datapath.send_msg(req)

        #applica meter_id=1 al flusso interessato
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
                                idle_timeout=0,
                                hard_timeout=10,
                                priority=3,
                                instructions=inst)
        
        print "limit flow entries in the table "
        datapath.send_msg(mod)
    '''

e=NetworkExecute()