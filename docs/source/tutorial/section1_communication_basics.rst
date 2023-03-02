************************
Communication basics
************************
In this section you will be introduced to the basics of sending and receiving both classical and quantum information.
As well as the first steps of writing programs and manipulating Qubits.

This chapter of the tutorial takes the user through the example ``tutorial_examples\1_communication-basics``.
This chapter will focus only on ``application.py`` file.
The example can be executed via:

.. code-block:: bash

   python run_simulation.py

Program basics
==============
A SquidASM program receives the objects it needs to send instructions to the quantum device controller or communications to other nodes via a ProgramContext object.
For this section we do not go into the details of ProgramContext and ProgramMeta.
This will be discussed in section :ref:`label_program_interface`.


.. code-block:: python
   :caption: application.py

   class AliceProgram(Program):
       PEER_NAME = "Bob"

       @property
       def meta(self) -> ProgramMeta:

       def run(self, context: ProgramContext):
           # get classical socket to peer
           csocket = context.csockets[self.PEER_NAME]
           # get EPR socket to peer
           epr_socket = context.epr_sockets[self.PEER_NAME]
           # get connection to quantum device controller
           connection = context.connection


Sending classical information
==============================
Classical information is done via the ``Socket`` object from ``netqasm.sdk``.
The Socket objects represent an open connection to a peer.
So sending a classical message to a peer may be done by using the ``send()`` method of the classical socket.

.. code-block:: python
   :caption: Alice

   message = "start protocol at time: xx:xx"
   csocket.send(message)
   print(f"Alice sends message: {message}")

In order for Bob to receive the message, he must be waiting for a classical message at the same time using the ``recv()`` method.

.. code-block:: python
   :caption: Bob

   message = yield from csocket.recv()
   print(f"Bob receives message: {message}")

It is mandatory to include the ``yield from`` keywords when receiving messages for the application to work with SquidASM.
For the full reason why this is required see section: :ref:`label_yield_from`.

TODO maybe not introduce StructuredMessages here?

The other way of sending messages is via ``StructuredMessages``, where there is also a header besides the payload.
We can use this to create a handshake that Bob has received the message from Alice.

.. code-block:: python
   :caption: Bob

   callback_message = StructuredMessage(header="echo", payload=message)
   csocket.send_structured(callback_message)
   print(f"Bob sends structured message with header: {callback_message.header}"
         f" and payload: {callback_message.payload}")

.. code-block:: python
   :caption: Alice

   callback_message = yield from csocket.recv_structured()
   print(f"Alice receives a structured message with header: {callback_message.header}"
        f" and payload: {callback_message.payload}")

   # Check the handshake received from Bob
   if callback_message.header != "echo" or callback_message.payload != message:
      raise Exception("Classical communication handshake failed")

Running the simulation should results in:

.. code-block:: text

   Alice sends message: start protocol at time: xx:xx
   Bob receives message start protocol at time: xx:xx
   Bob sends structured message with header: echo and payload: start protocol at time: xx:xx
   Alice receives a structured message with header: echo and payload: start protocol at time: xx:xx

creating EPR pairs between nodes
====================================
Creating an EPR pair follows a similar pattern as classical communication,
namely Alice must register a request using ``create_keep()`` to generate an EPR pair,
while Bob needs to be listening to such a request using ``recv_keep()``.

Both ``create_keep()`` and  ``recv_keep()`` return a list of qubits so we select our local EPR qubit using ``[0]``.
The default setting is that only a single EPR pair is generated,
but a request for multiple EPR pairs may be placed using ``create_keep(number=n)``.

.. code-block:: python
   :caption: Alice

   qubit = epr_socket.create_keep()[0]
   qubit.H()
   result = qubit.measure()
   yield from connection.flush()
   print(f"Alice measures local EPR qubit: {result}")


.. code-block:: python
   :caption: Bob

   qubit = epr_socket.recv_keep()[0]
   qubit.H()
   result = qubit.measure()
   yield from connection.flush()
   print(f"Bob measures local EPR qubit: {result}")

After the EPR pair is ready, we apply a Hadamard gate and measure the qubit.
It is then required to send these instructions to the quantum device controller using ``yield from connection.flush()`` for both Alice and Bob.
The next section, :ref:`label_netqasm_connection`, will go into more details regarding the connection.

Running the simulation results in either:

.. code-block:: text

   Alice measures local EPR qubit: 0
   Bob measures local EPR qubit: 0

or:

.. code-block:: text

   Alice measures local EPR qubit: 1
   Bob measures local EPR qubit: 1