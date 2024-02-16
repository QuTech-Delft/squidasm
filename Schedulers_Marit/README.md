README FILE MSC THESIS CODE MARIT TALSMA

@Michal:

What files did I create:
- fibre.py
- dtw_scheduler.py
- mw_scheduler.py
& I added some lines to your code setup where needed to be able to implement the fibre link setup

--> the working of the fibre link should speak for itself, namely it takes the inputs from both sides of the connection and calculated a final probability, time and fidelity. for the fidelity the calcualtion is done using Werner states so if you dont want this in the final setup this fidelity calculation should be changed.

--> for the mw scheduler: it works for all cases basically :)
--> for the dtw scheduler: it works for all cases minus the use of (resource node) multiplexing, this is because i had some struggles with the link events and therefore used the cycleendevent which stops all cycles at the next event call so when multiplexing and a request using one resource node is finished earlier than a request using another resource node, cycleendevent still stops both requests at the same time (and therefore the second one incorrectly prematurely). The use of the dynamic time window calculation i think also speaks for itself and can be modified by adding static delay (whatever the user might want that to be) which is defined in the DTWScheduleConfig file


Recommendations:
- Make the dtw scheduler usable for multiplexing
- Create the possibility to use different link types and different end node types within one setup (so lets say to one hub one fibre link with an NV is connected and also a general end node with a sattelite link) because now one can only specify one link type and one end node type for the entire system
- (optimizing user experience:) Let the setup feed parameters from one element of the setup into another in some sort of way where one can make certain design choices (as for for instance end node types, link types, etc) and from that fidelities, probabilities, etc are automatically generated and used by the setup without the user having to intervene (as would be the case for a real world network) 