# Copyright (C) 2016 Li Cheng at Beijing University of Posts
# and Telecommunications. www.muzixing.com
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
# http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or
# implied.
# See the License for the specific language governing permissions and
# limitations under the License.

from __future__ import division
import copy
from operator import attrgetter
from ryu import cfg
from ryu.base import app_manager
from ryu.base.app_manager import lookup_service_brick
from ryu.controller import ofp_event
from ryu.controller.handler import MAIN_DISPATCHER, DEAD_DISPATCHER
from ryu.controller.handler import CONFIG_DISPATCHER
from ryu.controller.handler import set_ev_cls
from ryu.ofproto import ofproto_v1_3
from ryu.lib import hub
from ryu.lib.packet import packet
import setting


import threading
from datetime import datetime
import time
from collections import deque
import numpy as np 

import network_knowledge
import network_plan

CONF = cfg.CONF


class NetworkMonitor(app_manager.RyuApp):
    """
        NetworkMonitor is a Ryu app for collecting traffic information.
    """
    OFP_VERSIONS = [ofproto_v1_3.OFP_VERSION]

    def __init__(self, *args, **kwargs):
        super(NetworkMonitor, self).__init__(*args, **kwargs)
        self.name = 'monitor'
        self.datapaths = {}
        self.port_stats = {}
        self.port_speed = {}
        self.flow_stats = {}
        self.flow_speed = {}
        self.my_dict = {}
        self.dd3 = {}
        self.list_speed = {}
        self.stats = {}
        self.port_features = {}
        self.free_bandwidth = {}
        self.topo_disc = lookup_service_brick('topo_disc')
        self.graph = None
        self.capabilities = None
        self.best_paths = None
        # Start to green thread to monitor traffic and calculating
        # free bandwidth of links respectively.
        self.monitor_thread = hub.spawn(self._monitor)
        self.save_freebandwidth_thread = hub.spawn(self._save_bw_graph)
        self.message_flow = []
        self.f = {}
        #self.sem_mon = threading.Semaphore(1)
       
        
    @set_ev_cls(ofp_event.EventOFPStateChange,
                [MAIN_DISPATCHER, DEAD_DISPATCHER])
    def _state_change_handler(self, ev):
        """
            Record datapath's info
        """
        datapath = ev.datapath
        if ev.state == MAIN_DISPATCHER:
            if not datapath.id in self.datapaths:
                self.logger.debug('register datapath: %016x', datapath.id)
                self.datapaths[datapath.id] = datapath
        elif ev.state == DEAD_DISPATCHER:
            if datapath.id in self.datapaths:
                self.logger.debug('unregister datapath: %016x', datapath.id)
                del self.datapaths[datapath.id]
    
    def _monitor(self):
        """
            Main entry method of monitoring traffic.
        """
        while CONF.weight == 'bw':
            self.stats['flow'] = {}
            self.stats['port'] = {}
            for dp in self.datapaths.values():
                self.port_features.setdefault(dp.id, {})
                self._request_stats(dp)
                # refresh data.
                self.capabilities = None
                self.best_paths = None
            hub.sleep(setting.MONITOR_PERIOD)
            if self.stats['flow'] or self.stats['port']:
                self.show_stat('flow')
                self.show_stat('port')
                #self.analyze('flow')
                hub.sleep(1)
            self.analyze('flow')
            print("ANALIZZATORE PARTITO")

    def analyze(self, type):
        print("ANALIZZANDO..")

        # print("Sem Mon")
        # network_knowledge.nk.sem_mon.acquire()

        somma = 0

        '''
            Show statistics info according to data type.
            type: 'port' 'flow'
        '''
        if setting.TOSHOW is False:
            return

        bodys = self.stats[type]
        if(type == 'flow' ):
            print('Sto analizzando i flussi')
            print('------------------------------------------------------------------')
     
            for dpid in bodys.keys():
                
                for stat in sorted(
                    [flow for flow in bodys[dpid] if flow.priority == 1],
                    key=lambda flow: (flow.match.get('in_port'), #flow.match.get('ipv4_src'),
                                      flow.match.get('ipv4_dst'))):
                                        
                    d = self.flow_speed[dpid]
                    #print d                                            
                    for k in d.keys():
                        #print "Velocita di ", k, " : ", d[k][0]        

                        if (k in self.f.keys()):
                            fs = self.f[k]
                        else:
                            fs = []

                        fs.insert(0, d[k][0])
                        if (len(fs) > 5):
                            fs.pop()

                        self.f[k] = fs

                        '''
                        calcolo somma delle velocita 
                        degli ultimi 5 istanti temporali
                        ''' 

                        for i in range(len(fs)):
                            somma += fs[i]
                
                        if (stat.match['ipv4_dst'] == '10.0.0.1'):
                    


                            flow_ts = datetime.now()


                            
                            network_knowledge.nk.add_speed(stat.match['ipv4_src'], self.datapaths[dpid], stat.match['in_port'], flow_ts, fs)
                            #network_knowledge.nk.add_host_to_dict(stat.match['ipv4_src'], fs)

                            print("Sem Mon")
                            network_knowledge.nk.sem_mon.acquire()

                            print ('self.sem_plan.acquire()')
                            network_knowledge.nk.sem_plan.release()
                            print ('self.sem_plan.acquire()')

                            #calcolo media ponderata velocita
                            m = network_knowledge.nk.dict_speed
                            #myDict = {'A':['asdasd', 2, 3], 'B':['asdasd', 4, 5], 'C':['rgerg', 9, 10]}
                            #normConst = 0.7
                            #avg = sum(sum([m[x][-1]*normConst) / float(normConst) for x in network_knowledge.nk.dict_speed.items()])
                            #avg = np.average([val[-1] for val in m], axis=1, weights=normConst)
                            #avg = [sum(val[-1] for val in m)/5]
                            #avg = abs(sum(m[0][:5])/5)[val[1] for val in m ]
                            #avg = [sum(m[1] for k in m)/5]
                            #results = sum([x[:5] for x in m])/5
                            #avg =  sum(x[1][:5] for x in m) / 5
                            #print avg
                            '''
                            for k, v in m.items():
                                if (len(v) < 5):
                                    print ("Niente")
                                else: 
                                    avg = abs(sum(v)/5)
                                    network_knowledge.nk.dict_avg[k] = avg
                                    print (">>>>>>>" + str(network_knowledge.nk.dict_avg)) 
                            '''
                            network_knowledge.nk.dict_avg = dict([(key, sum(values)/5) for key, values in m.items()])
                            print m
                            print ('dizionario media ' + str(network_knowledge.nk.dict_avg))   

                            print ('sem_plan.release()')
                            network_knowledge.nk.sem_plan.release()
                            print ('fatto')          
                            
                        else: 
                            pass                    

                print '\n'

    
    def _save_bw_graph(self):
        """
            Save bandwidth data into networkx graph object.
        """
        while CONF.weight == 'bw':
            self.graph = self.create_bw_graph(self.free_bandwidth)
            self.logger.debug("save_freebandwidth")
            hub.sleep(setting.MONITOR_PERIOD)

    def _request_stats(self, datapath):
        """
            Sending request msg to datapath
        """
        self.logger.debug('send stats request: %016x', datapath.id)
        ofproto = datapath.ofproto
        parser = datapath.ofproto_parser

        req = parser.OFPPortDescStatsRequest(datapath, 0)
        datapath.send_msg(req)

        req = parser.OFPPortStatsRequest(datapath, 0, ofproto.OFPP_ANY)
        datapath.send_msg(req)

        req = parser.OFPFlowStatsRequest(datapath)
        datapath.send_msg(req)

    def get_min_bw_of_links(self, graph, path, min_bw):
        """
            Getting bandwidth of path. Actually, the mininum bandwidth
            of links is the bandwith, because it is the neck bottle of path.
        """
        _len = len(path)
        if _len > 1:
            minimal_band_width = min_bw
            for i in xrange(_len-1):
                pre, curr = path[i], path[i+1]
                if 'bandwidth' in graph[pre][curr]:
                    bw = graph[pre][curr]['bandwidth']
                    minimal_band_width = min(bw, minimal_band_width)
                else:
                    continue
            return minimal_band_width
        return min_bw

    def get_best_path_by_bw(self, graph, paths):
        """
            Get best path by comparing paths.
        """
        capabilities = {}
        best_paths = copy.deepcopy(paths)

        for src in paths:
            for dst in paths[src]:
                if src == dst:
                    best_paths[src][src] = [src]
                    capabilities.setdefault(src, {src: setting.MAX_CAPACITY})
                    capabilities[src][src] = setting.MAX_CAPACITY
                    continue
                max_bw_of_paths = 0
                best_path = paths[src][dst][0]
                for path in paths[src][dst]:
                    min_bw = setting.MAX_CAPACITY
                    min_bw = self.get_min_bw_of_links(graph, path, min_bw)
                    if min_bw > max_bw_of_paths:
                        max_bw_of_paths = min_bw
                        best_path = path

                best_paths[src][dst] = best_path
                capabilities.setdefault(src, {dst: max_bw_of_paths})
                capabilities[src][dst] = max_bw_of_paths
        self.capabilities = capabilities
        self.best_paths = best_paths
        return capabilities, best_paths

    def create_bw_graph(self, bw_dict):
        """
            Save bandwidth data into networkx graph object.
        """
        try:
            graph = self.topo_disc.graph
            link_to_port = self.topo_disc.link_to_port
            for link in link_to_port:
                (src_dpid, dst_dpid) = link
                (src_port, dst_port) = link_to_port[link]
                if src_dpid in bw_dict and dst_dpid in bw_dict:
                    bw_src = bw_dict[src_dpid][src_port]
                    bw_dst = bw_dict[dst_dpid][dst_port]
                    bandwidth = min(bw_src, bw_dst)
                    # add key:value of bandwidth into graph.
                    graph[src_dpid][dst_dpid]['bandwidth'] = bandwidth
                else:
                    graph[src_dpid][dst_dpid]['bandwidth'] = 0
            return graph
        except:
            self.logger.info("Create bw graph exception")
            if self.topo_disc is None:
                self.topo_disc = lookup_service_brick('topo_disc')
            return self.topo_disc.graph

    def _save_freebandwidth(self, dpid, port_no, speed):
        # Calculate free bandwidth of port and save it.
        port_state = self.port_features.get(dpid).get(port_no)
        if port_state:
            capacity = port_state[2]
            curr_bw = self._get_free_bw(capacity, speed)
            self.free_bandwidth[dpid].setdefault(port_no, None)
            self.free_bandwidth[dpid][port_no] = curr_bw
        else:
            self.logger.info("Fail in getting port state")

    def _save_stats(self, _dict, key, value, length):
        if key not in _dict:
            _dict[key] = []
        _dict[key].append(value)

        if len(_dict[key]) > length:
            _dict[key].pop(0)

    def _save_stats1(self, _dict, key, value, length):
        if key not in _dict:
            _dict[key] = []
        _dict[key].append(value)

        if len(_dict[key]) > length:
            _dict[key].pop(0)

    def _get_speed(self, now, pre, period):
        if period:
            return (now - pre) / (period)
        else:
            return 0

    def _get_free_bw(self, capacity, speed):
        # BW:Mbit/s
        return max(capacity/10**3 - speed * 8/10**6, 0)

    def _get_time(self, sec, nsec):
        return sec + nsec / (10 ** 9)

    def _get_period(self, n_sec, n_nsec, p_sec, p_nsec):
        return self._get_time(n_sec, n_nsec) - self._get_time(p_sec, p_nsec)

    @set_ev_cls(ofp_event.EventOFPFlowStatsReply, MAIN_DISPATCHER)
    def _flow_stats_reply_handler(self, ev):
        """
            Save flow stats reply info into self.flow_stats.
            Calculate flow speed and Save it.
        """
        counter = 0
        body = ev.msg.body
        dpid = ev.msg.datapath.id
        self.stats['flow'][dpid] = body
        self.flow_stats.setdefault(dpid, {})
        self.flow_speed.setdefault(dpid, {})
        for stat in sorted([flow for flow in body if flow.priority == 1],
                           key=lambda flow: (flow.match.get('in_port'),
                                             flow.match.get('ipv4_dst'))):
            key = (stat.match['in_port'],  stat.match.get('ipv4_dst'),
                   stat.instructions[0].actions[0].port)
            value = (stat.packet_count, stat.byte_count,
                     stat.duration_sec, stat.duration_nsec)
            self._save_stats(self.flow_stats[dpid], key, value, 5)

            # Get flow's speed.
            pre = 0
            period = setting.MONITOR_PERIOD
            tmp = self.flow_stats[dpid][key]
            if len(tmp) > 1:
                pre = tmp[-2][1]
                period = self._get_period(tmp[-1][2], tmp[-1][3],
                                          tmp[-2][2], tmp[-2][3])

            speed = self._get_speed(self.flow_stats[dpid][key][-1][1],
                                    pre, period)

            self._save_stats(self.flow_speed[dpid], key, speed, 5)



            #print ">>> flow stats ", self.flow_stats[dpid][key]
            #print ">>> flow speed ", self.flow_speed[dpid][key]
        
    

    @set_ev_cls(ofp_event.EventOFPPortStatsReply, MAIN_DISPATCHER)
    def _port_stats_reply_handler(self, ev):
        """
            Save port's stats info
            Calculate port's speed and save it.
        """
        body = ev.msg.body
        dpid = ev.msg.datapath.id
        self.stats['port'][dpid] = body
        self.free_bandwidth.setdefault(dpid, {})

        for stat in sorted(body, key=attrgetter('port_no')):
            port_no = stat.port_no
            if port_no != ofproto_v1_3.OFPP_LOCAL:
                key = (dpid, port_no)
                value = (stat.tx_bytes, stat.rx_bytes, stat.rx_errors,
                         stat.duration_sec, stat.duration_nsec)

                self._save_stats(self.port_stats, key, value, 5)

                # Get port speed.
                pre = 0
                period = setting.MONITOR_PERIOD
                tmp = self.port_stats[key]
                if len(tmp) > 1:
                    pre = tmp[-2][0] + tmp[-2][1]
                    period = self._get_period(tmp[-1][3], tmp[-1][4],
                                              tmp[-2][3], tmp[-2][4])

                speed = self._get_speed(
                    self.port_stats[key][-1][0] + self.port_stats[key][-1][1],
                    pre, period)

                self._save_stats(self.port_speed, key, speed, 5)
                self._save_freebandwidth(dpid, port_no, speed)
                #print ">>>>>>>>>>>", self.port_speed

    @set_ev_cls(ofp_event.EventOFPPortDescStatsReply, MAIN_DISPATCHER)
    def port_desc_stats_reply_handler(self, ev):
        """
            Save port description info.
        """
        msg = ev.msg
        dpid = msg.datapath.id
        ofproto = msg.datapath.ofproto

        config_dict = {ofproto.OFPPC_PORT_DOWN: "Down",
                       ofproto.OFPPC_NO_RECV: "No Recv",
                       ofproto.OFPPC_NO_FWD: "No Farward",
                       ofproto.OFPPC_NO_PACKET_IN: "No Packet-in"}

        state_dict = {ofproto.OFPPS_LINK_DOWN: "Down",
                      ofproto.OFPPS_BLOCKED: "Blocked",
                      ofproto.OFPPS_LIVE: "Live"}

        ports = []
        for p in ev.msg.body:
            ports.append('port_no=%d hw_addr=%s name=%s config=0x%08x '
                         'state=0x%08x curr=0x%08x advertised=0x%08x '
                         'supported=0x%08x peer=0x%08x curr_speed=%d '
                         'max_speed=%d' %
                         (p.port_no, p.hw_addr,
                          p.name, p.config,
                          p.state, p.curr, p.advertised,
                          p.supported, p.peer, p.curr_speed,
                          p.max_speed))

            if p.config in config_dict:
                config = config_dict[p.config]
            else:
                config = "up"

            if p.state in state_dict:
                state = state_dict[p.state]
            else:
                state = "up"

            port_feature = (config, state, p.curr_speed)
            self.port_features[dpid][p.port_no] = port_feature

    @set_ev_cls(ofp_event.EventOFPPortStatus, MAIN_DISPATCHER)
    def _port_status_handler(self, ev):
        """
            Handle the port status changed event.
        """
        msg = ev.msg
        reason = msg.reason
        port_no = msg.desc.port_no
        dpid = msg.datapath.id
        ofproto = msg.datapath.ofproto


        reason_dict = {ofproto.OFPPR_ADD: "added",
                       ofproto.OFPPR_DELETE: "deleted",
                       ofproto.OFPPR_MODIFY: "modified", }

        if reason in reason_dict:

            print "switch%d: port %s %s" % (dpid, reason_dict[reason], port_no)
        else:
            print "switch%d: Illeagal port state %s %s" % (port_no, reason)

    def show_stat(self, type):
        '''
            Show statistics info according to data type.
            type: 'port' 'flow'
        '''
        if setting.TOSHOW is False:
            return

        bodys = self.stats[type]
        if(type == 'flow'):
            print('datapath         ''   in-port      ip-src            ip-dst       '
                  'out-port packets  bytes  flow-speed(B/s)')
            print('---------------- ''  -------- ----------------- ----------------- '
                  '-------- -------- -------- -----------')
            for dpid in bodys.keys():
                for stat in sorted(
                    [flow for flow in bodys[dpid] if flow.priority == 1],
                    key=lambda flow: (flow.match.get('ipv4_src'), #??
                                      flow.match.get('in_port'),
                                      flow.match.get('ipv4_dst'))):
                    #print stat                                                                     #\\\\\\\\\\\\\\\\\\\\\\
                    print('%016x %8x %17s %17s %8x %8d %8d %8.1f' % (
                        dpid,
                        stat.match['in_port'], stat.match['ipv4_src'], #??
                        stat.match['ipv4_dst'],
                        stat.instructions[0].actions[0].port,
                        stat.packet_count, stat.byte_count,
                        abs(self.flow_speed[dpid][
                            (stat.match.get('in_port'),
                            stat.match.get('ipv4_dst'),
                            stat.instructions[0].actions[0].port)][-1])))
            print '\n'

        if(type == 'port'):
            print('datapath             port   ''rx-pkts  rx-bytes rx-error '
                  'tx-pkts  tx-bytes tx-error  port-speed(B/s)'
                  ' current-capacity(Kbps)  '
                  'port-stat   link-stat')
            print('----------------   -------- ''-------- -------- -------- '
                  '-------- -------- -------- '
                  '----------------  ----------------   '
                  '   -----------    -----------')
            format = '%016x %8x %8d %8d %8d %8d %8d %8d %8.1f %16d %16s %16s'
            for dpid in bodys.keys():
                for stat in sorted(bodys[dpid], key=attrgetter('port_no')):
                    if stat.port_no != ofproto_v1_3.OFPP_LOCAL:
                        print(format % (
                            dpid, stat.port_no,
                            stat.rx_packets, stat.rx_bytes, stat.rx_errors,
                            stat.tx_packets, stat.tx_bytes, stat.tx_errors,
                            abs(self.port_speed[(dpid, stat.port_no)][-1]),
                            self.port_features[dpid][stat.port_no][2],
                            self.port_features[dpid][stat.port_no][0],
                            self.port_features[dpid][stat.port_no][1]))
            print '\n'





'''
#Gia inserito nel plan
if ((somma/5) > setting.MAX_SPEED):                 
    print('>>>[Warning] - il flusso sulla porta [src_port = '+ str(stat.match['in_port']) +'] ' + 
        'con sorgente [ip_src = ' + str(stat.match['ipv4_src']) +'] ' + 
        'e destinazione [ip_dst = ' + str(stat.match['ipv4_dst']) +'] ' + 
        'deve essere bloccato')
    print('--> chiama il --plan()--')
    print '\n' 
'''   


'''
list_speed.append(abs(self.flow_speed[dpid][
        (stat.match.get('in_port'),
        stat.match.get('ipv4_dst'),
        stat.instructions[0].actions[0].port)][-1]))
list_speed.popleft()
print(list_speed)
'''
'''
#aggiunta valori alla lista
flow_key = (stat.match.get('in_port'),
        stat.match.get('ipv4_dst'),
        stat.instructions[0].actions[0].port)
print "dpid=", dpid, "; flow_key=", flow_key, "; speed=", self.flow_speed[dpid][flow_key][-1]
speed = abs(self.flow_speed[dpid][flow_key][-1])
my_list1 = [dpid]
my_list2 = [flow_key]
my_list3 = [speed]
#my_list4 = []
my_dict = {"datapath": [my_list1], "inoutports-dest": [my_list2], "speeds": [my_list3]}
#my_dict = {dpid, flow_key, speed}
print "Dizionario 1:", my_dict


if self.flow_speed[dpid][flow_key][-1] > 1310720 and i < 5 :
    i = i+1
elif i>5:
    print ">>>overflow<<<"
'''


'''
my_dict[{[my_list1][my_list2][my_list3][4]}] = my_dict[{[my_list1][my_list2][my_list3][3]}]
my_dict[{[my_list1][my_list2][my_list3][3]}] = my_dict[{[my_list1][my_list2][my_list3][2]}]
my_dict[{[my_list1][my_list2][my_list3][2]}] = my_dict[{[my_list1][my_list2][my_list3][1]}]
my_dict[{[my_list1][my_list2][my_list3][1]}] = my_dict[{[my_list1][my_list2][my_list3][0]}]

print "Dizionariodopociclo:", my_dict
'''

#my_dict[{dpid, flow_key, speed[4]}] = my_dict[{dpid, flow_key, speed[3]}]
#my_dict[{dpid, flow_key, speed[3]}] = my_dict[{dpid, flow_key, speed[2]}]
#my_dict[{dpid, flow_key, speed[2]}] = my_dict[{dpid, flow_key, speed[1]}]
#my_dict[{dpid, flow_key, speed[1]}] = my_dict[{dpid, flow_key, speed[0]}]
#my_dict[{dpid, flow_key, speed[0]}] = my_dict[{my_list1, my_list2, my_list3}]


#list_speed[{"dpid": dpid}, [flow_key][4]=list_speed[{"dpid": dpid}, [flow_key][3]]
#list_speed[{"dpid": dpid}, [flow_key][3]=list_speed[{"dpid": dpid}, [flow_key][2]
#list_speed[{"dpid": dpid}, [flow_key][2]=list_speed[{"dpid": dpid}, [flow_key][1]
#list_speed[{"dpid": dpid}, [flow_key][1]=list_speed[{"dpid": dpid}, [flow_key][0]
#list_speed[{"dpid": dpid}, [flow_key][0]=list_speed[{"dpid": dpid}, [flow_key][0]abs(self.flow_speed[dpid][flow_key][-1])
#self.list_speed[{"dpid": dpid}, {"flow_key": flow_key}, {"speed": self.flow_speed[dpid][flow_key][-1]}]

    #i = i+1
    #time.sleep(5) #delay 5 secondi per riempire l'array


#somma velocita ultimi 5 secondi
'''
if (sum(list_speed[dpid][flow_key][5:]) > 6553600):                 
    print('[Warning] - il flusso sulla porta [src_port = '+ str(stat.match['in_port']) +'] ' + 'con sorgente [ip_src = ' + str(stat.match['ipv4_src']) +'] ' + 'e destinazione [ip_dst = ' + str(stat.match['ipv4_dst']) +'] ' + 'deve essere bloccato')
    print('--> chiama il --plan()--')
    print '\n' 
print(self.list_speed)
    

#prova con il while
while (sum(list_speed[dpid][flow][3:]) > 6553600):
    
    list_speed[dpid][flow][4]=list_speed[dpid][flow][3]
    list_speed[dpid][flow][3]=list_speed[dpid][flow][2]
    list_speed[dpid][flow][2]=list_speed[dpid][flow][1]
    list_speed[dpid][flow][1]=list_speed[dpid][flow][0]
    list_speed[dpid][flow][0]=abs(self.flow_speed[dpid][
            (stat.match.get('in_port'),
            stat.match.get('ipv4_dst'),
            stat.instructions[0].actions[0].port)][-1])
    
print('[Warning] - il flusso sulla porta [src_port = '+ str(stat.match['in_port']) +'] ' + 'con sorgente [ip_src = ' + str(stat.match['ipv4_src']) +'] ' + 'e destinazione [ip_dst = ' + str(stat.match['ipv4_dst']) +'] ' + 'deve essere bloccato')
print('--> chiama il --plan()--')
print '\n'
print(list_speed)
'''

#se flusso >10Mbps chiama il plan
#1310720B/s = 10Mbps

'''
if (abs(self.flow_speed[dpid][
        (stat.match.get('in_port'),
        stat.match.get('ipv4_dst'),
        stat.instructions[0].actions[0].port)][-1]) > 1310720 and counter < 5):
    counter = counter + 1
    print counter
elif (abs(self.flow_speed[dpid][
        (stat.match.get('in_port'),
        stat.match.get('ipv4_dst'),
        stat.instructions[0].actions[0].port)][-1]) > 1310720 and counter > 5):
    print('[Warning] - il flusso sulla porta [src_port = '+ str(stat.match['in_port']) +'] ' + 'con sorgente [ip_src = ' + str(stat.match['ipv4_src']) +'] ' + 'e destinazione [ip_dst = ' + str(stat.match['ipv4_dst']) +'] ' + 'deve essere bloccato')
    print('--> chiama il --plan--')
    print '\n'
else :
    return
'''
            













'''
    def src_counter(self, packet):
        if packet['ip_src'] in self.src_count:
            self.src_count[packet['ip_src']] += 1
            if self.src_count[packet['ip_src']] > 10000:
                self.create_blocking_flow(packet['ip_src'])            

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
class Sniffer(mp.Process):
    def __init__(self, q, dev_='eth0'):
        super(Sniffer, self).__init__()
        self.q = q
        self.dev = dev_
        print 'sniffer started'

    def run(self):
        p = pcap.pcapObject()
        # Get only the first 320 bits of the packet.
        p.open_live(self.dev, 320, 1, 0)

        def dump(pktlen, data, timestamp):
            self.q.put((pktlen, data, timestamp))

        try:
            while True:
                p.dispatch(1, dump)
        except KeyboardInterrupt:
            pass
        print 'PCAP STATS: ' + repr(p.stats())

##################

class Parser():
    def __init__(self, in_q, out_q):
        self.in_q = in_q
        self.out_q = out_q

    @staticmethod
    def parse(pktlen, data, timestamp):
        packet = {'len': pktlen, 'time': timestamp}
        eth = dpkt.ethernet.Ethernet(data)
        ip = eth.data

        def get_mac_addr(_mac):
            maclist = []
            for Z in range(12/2):
                maclist.append(_mac[Z*2:Z*2+2])
            mac = ":".join(maclist)
            return mac

        if isinstance(ip, dpkt.ip.IP):
            data = ip.data
            packet['type'] = data.__class__.__name__.lower()
            packet['ip_src'] = socket.inet_ntoa(ip.src)
            packet['ip_dst'] = socket.inet_ntoa(ip.dst)
            packet['mac_src'] = get_mac_addr(binascii.hexlify(eth.src))
            packet['mac_dst'] = get_mac_addr(binascii.hexlify(eth.dst))
        else:
            return
        if isinstance(data, dpkt.tcp.TCP) or isinstance(data, dpkt.udp.UDP):
            packet['port_src'] = data.sport
            packet['port_dst'] = data.dport
            # packet['seq'] = data.seq
            # packet['ack'] = data.ack
            # packet['flags'] = data.flags
            packet['icmp_code'] = "''"
        elif isinstance(data, dpkt.icmp.ICMP):
            packet['port_src'] = "''"
            packet['port_dst'] = "''"
            packet['icmp_code'] = data.code
        else:
            return
        return packet

    def run(self):
        while True:
            eventlet.sleep(0)
            try:
                item = self.in_q.get(True, 0.05)
                if item is None:
                    continue
                parsed = self.parse(item[0], item[1], item[2])
                self.out_q.put(parsed)
            except eventlet.queue.Empty:
                pass

class Counter():
    def __init__(self, q):
        self.q = q
        self.dst_count = {}
        self.src_count = {}
        self.ratio_count = {}
        self.block_packet_count = {}
        self.seqcounter = {}
        self.blocked_sources = []
        self.already_blocked = []

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

    def dst_counter(self, packet):
        if packet['ip_dst'] in self.dst_count:
            self.dst_count[packet['ip_dst']] += 1
        else:
            self.dst_count[packet['ip_dst']] = 1

    def src_counter(self, packet):
        if packet['ip_src'] in self.src_count:
            self.src_count[packet['ip_src']] += 1
            if self.src_count[packet['ip_src']] > 10000:
                self.create_blocking_flow(packet['ip_src'])
        else:
            self.src_count[packet['ip_src']] = 1

    def highest_counter(self):
        if len(self.dst_count) > 0:
            target = max(self.dst_count.iteritems(), key=operator.itemgetter(1))
            print 'target: {0}: {1}'.format(target[0], target[1])
        else:
            print 'dst_count empty'

    def ratio_counter(self, packet):
        pair_list = sorted([packet['ip_src'], packet['ip_dst']])
        pair = '-'.join(pair_list)
        if pair in self.ratio_count:
            self.ratio_count[pair][packet['ip_src']] += 1
            ratio = float(self.ratio_count[pair][pair_list[0]]) / float(self.ratio_count[pair][pair_list[1]])
            self.ratio_count[pair]['ratio'] = ratio
            if ratio > 1000:
                self.create_blocking_flow(packet['ip_src'])
        else:
            self.ratio_count[pair] = {packet['ip_src']: 1, packet['ip_dst']: 1, 'ratio': 1}

    def bad_ratios(self):
        ratios = list((k, v['ratio']) for k, v in self.ratio_count.items() if v['ratio'] > 50)
        if len(ratios) > 0:
            for i in ratios:
                print 'Bad ratio: {0}: {1}'.format(i[0].split('-')[0], i[1])
        else:
            print 'No bad ratios'

    def outgoing_block_v1(self, packet):
    # Outgoing_block_V1 starts sampling from the moment we pushed the block flow.
        mac_dst = packet['mac_dst']

        if mac_dst in outgoing_block_mode_v1_dict:
            packet_time = packet['time'] * 1000  # msec
            if packet_time > outgoing_block_mode_v1_dict[mac_dst]:
                pair_list = sorted([packet['ip_src'], packet['ip_dst']])
                pair = '-'.join(pair_list)
                if pair in self.block_packet_count:
                    if time.time() - self.block_packet_count[pair]['last_update'] > 60:
                         # These results weren't updated for over 2 seconds. Reset first.
                        self.block_packet_count[pair][packet['ip_src']] = 1
                        self.block_packet_count[pair]['last_update'] = time.time()

                    self.block_packet_count[pair][packet['ip_src']] += 1
                    ratio = float(self.block_packet_count[pair][pair_list[0]]) / \
                        float(self.block_packet_count[pair][pair_list[1]])
                    self.block_packet_count[pair]['ratio'] = ratio
                    self.block_packet_count[pair]['last_update'] = time.time()

                   # If we receive more than X packets while knowing we didn't reply:
                    if ratio > 10000:
                        print "blocking ", packet['ip_src']
                        self.create_blocking_flow(packet['ip_src'])

                else:
                    self.block_packet_count[pair] = {packet['ip_src']: 1, packet['ip_dst']: 1,
                                                     'ratio': 1, 'last_update': time.time()}
        else:
            print "We're not supposed to sample this packet..."

    def outgoing_block_v2(self, packet):
        #First sample for X seconds knowing that its non-blocked traffic,
        # then sample the packages that we know should been blocked by the outgoing drop flow
        # as the higher priority flow mod was dropped by the switch's timeout.
        mac_dst = packet['mac_dst']
        if mac_dst in outgoing_block_mode_v2_dict:
            packet_time = int(packet['time'] * 1000)  # msec
            pair_list = sorted([packet['ip_src'], packet['ip_dst']])
            pair = '-'.join(pair_list)
            if outgoing_block_mode_v2_dict[mac_dst][0] < packet_time < \
                    (outgoing_block_mode_v2_dict[mac_dst][0] + 2000):  # 2000 ms
                # Dump counters into class dict while keeping note of time, resetting if data is too old.
                if pair in self.block_packet_count:
                    # Reset old data (older than 30 seconds)
                    if self.block_packet_count[pair]['time_created'] < (time.time() - 30):
                        self.block_packet_count[pair] = {'packets_before': 1, 'packets_after': 1,
                                                         'time_created': time.time()}
                    else:
                        self.block_packet_count[pair]['packets_before'] += 1
                else:
                    self.block_packet_count[pair] = {'packets_before': 1, 'packets_after': 1,
                                                     'time_created': time.time()}

            block_time = outgoing_block_mode_v2_dict[mac_dst][0] + 2000
            if packet_time > block_time:
                if not pair in self.block_packet_count:
                    pass
                else:
                    if block_time < packet_time < (block_time + 250):
                        # First 250 ms after installing block flow is discarded
                        pass
                    elif packet_time > block_time and (block_time + 250) < packet_time < (block_time + 750):
                        self.block_packet_count[pair]['packets_after'] += 1
                    elif (block_time + 750) < packet_time < (block_time + 1100):
                        # Last 250 ms is used to trigger the final check to decide wether to
                        # block the source from this packet or not.
                        p_before = self.block_packet_count[pair]['packets_before']
                        # Check if packet tresholds are met:
                        if p_before > 1000:
                            ratio = float(self.block_packet_count[pair]['packets_before']) \
                                / float((self.block_packet_count[pair]['packets_after'] * 4))
                        else:
                            # If treshold is not met we will not block.
                            ratio = 1
                        if ratio < 5:
                            ## Switch flood protection
                            if not packet['ip_src'] in self.already_blocked:
                                self.create_blocking_flow(packet['ip_src'])
                                self.already_blocked.append(packet['ip_src'])
                                print "Created blocking flow for: ", packet['ip_src']

    def run(self):
        while True:
            eventlet.sleep(0)
            try:
                packet = self.q.get(True, 0.05)
                if packet is None:
                    continue
            except eventlet.queue.Empty:
                continue

            if mode == 1:
                self.dst_counter(packet)
            elif mode == 2:
                self.ratio_counter(packet)
            elif mode == 3:
                self.dst_counter(packet)
                self.ratio_counter(packet)
            elif mode == 4:
                self.src_counter(packet)
            elif mode == 5:
                self.outgoing_block_v1(packet)
            elif mode == 6:
                self.outgoing_block_v2(packet)

sniffer = Sniffer(unparsed_q, dev)
sniffer.start()
parser = Parser(unparsed_q, parsed_q)
counter = Counter(parsed_q)
'''
