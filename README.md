Indice del progetto:

1. network_monitor : 

NetworkMonitor is a Ryu app for collecting traffic information.

2. network_plan : 

Questa app fornisce un elenco di azioni da intraprendere nel caso in cui l'analizzatore dovesse rilevare traffico sospetto.

3. network_execute :

Il modulo execute riceve i parametri dal plan ed esegue le operazioni sui flussi, in base alle decisioni intraprese dal plan. Consuma la coda action_queue e poi una volta eseguita l'operazione la elimina.

4. network_knowledge :

Il modulo condiviso knowledge contiene la conoscienza, ossia i dati raccolti dall' analizzatore e i dati da passare al modulo execute.
    
5. shortest_forwarding --> network_main_ddos : 

network_main_ddos is a Ryu app for forwarding packets in shortest path.
This App does not defined the path computation method.
To get shortest path, this module depends on network topo_disc, network monitor and network delay detecttor modules.

6. network_delay_detector : 

NetworkDelayDetector is a Ryu app for collecting link delay.

7. network_awareness--> network_topo_disc :

network_topo_disc is a Ryu app for discover topology information.
This App can provide many data services for other App, such as link_to_port, access_table, switch_port_table,access_ports, interior_ports,topology graph and shorteest paths.
