from threading import Thread
from Queue import Queue
from ryu.base import app_manager
from ryu.ofproto import ofproto_v1_3


import collections

import network_monitor
import network_plan
import threading


#coda con i vari valori dei flussi, man mano che vengono consumati dal plan essi vengono eliminati
#[[[5valori], ip1, ip2, ts], [[5valori], ip1, ip2, ts], ...]

class MessageQueue(app_manager.RyuApp):

    """A sample implementation of a First-In-First-Out
       data structure.
    """
    
    OFP_VERSIONS = [ofproto_v1_3.OFP_VERSION]

    def __init__(self, *args, **kwargs):
        super(MessageQueue, self).__init__(*args, **kwargs)
        self.name = 'queue'
        # semaforo 0
        self.semaphore = threading.Semaphore(0)
        self.in_stack = []
        self.out_stack = []

    def push(self, obj):
        self.in_stack.append(obj)
        # up semaforo
        self.semaphore.release()
        
    def pop(self):
        # down semaforo
        self.semaphore.acquire() #prima dell eliminazione dell elemento
        if not self.out_stack:
            self.in_stack.reverse()
            self.out_stack = self.in_stack
            self.in_stack = []
        return self.out_stack.pop()
    

q=MessageQueue()