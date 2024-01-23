Server example
++++++++++++++
This example shows how to create a server that can process incoming requests from multiple clients,
puts these requests on a queue and will execute these requests one by one.

DISCLAIMER
============
This example uses Netsquid Protocols in order to create listeners for each classical socket and other functionalities.
In a setting where one runs an application on hardware, one would, for example, start and use a thread for each listener.
But in SquidASM one can not create a functional application in the same fashion due the underlying discrete event simulator, Netsquid.
In this example, the appropriate Netsquid Protocols have been created to achieve the desired functionality,
but as these do not translate to hardware, any application written using them will require a larger translation to be compatible with hardware.
