#!/bin/bash

cd /home/ubuntu/ryu/ryu/app/network_awareness/
ryu-manager network_main_ddos.py --observe-links --k-paths=2 --weight=bw

cd
sudo mn --topo single,3 --mac --switch user --controller remote

ofsoftswitch (supporta i meter)
    sudo dpctl tcp:127.0.0.1:6634 stats-meter

openvswith (non supporta meter)
    sudo ovs-ofctl -O OpenFlow13 dump-meters s1

    sudo ovs-ofctl -O OpenFlow13 add-meter s1 meter=1,kbps,burst,band=type=drop,rate=10,burst_size=10
