import network_plan
import network_execute
import network_monitor
from ryu.base import app_manager
from ryu.ofproto import ofproto_v1_3

import threading


class ActionQueue(app_manager.RyuApp):

    """A sample implementation of a First-In-First-Out
       data structure.
    """
    
    OFP_VERSIONS = [ofproto_v1_3.OFP_VERSION]

    def __init__(self, *args, **kwargs):
        super(ActionQueue, self).__init__(*args, **kwargs)
        self.name = 'action'
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

aq=ActionQueue()