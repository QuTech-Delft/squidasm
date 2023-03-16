.. _label_program_interface:

.. role:: python(code)
  :language: python
  :class: highlight

************************
Simulation control
************************
In this section we explain the ``run_simulation.py`` file and the interface that programs in
``application.py`` must adhere to, ways to get output results from the program and logging.

The first sections will use the example: ``tutorial_examples\1_Basics`` for the code snippets.

Basics run_simulation file
=================================
The ``tutorial_examples\1_Basics\run_simulation.py`` file contains the minimal requirements to run a simulation:

.. code-block:: python
   :caption: tutorial_examples\\1_Basics\\run_simulation.py

    from squidasm.run.stack.config import StackNetworkConfig
    from squidasm.run.stack.run import run
    from application import AliceProgram, BobProgram

    # import network configuration from file
    cfg = StackNetworkConfig.from_file("config.yaml")

    # Create instances of programs to run
    alice_program = AliceProgram()
    bob_program = BobProgram()

    # Run the simulation. Programs argument is a mapping of network node labels to programs to run on that node
    run(config=cfg,
        programs={"Alice": alice_program, "Bob": bob_program},
        num_times=1)

In the ``run_simulation.py`` file one must first import the ``AliceProgram`` and ``BobProgram``.
These classes are used to create instances of the programs.
Afterwards the network configuration needs to be loaded from a file into a variable.

In the last step, running the simulation, we also define what node must run what program.
This is done using a python dictionary using the node names as key with the program instances as value.
Running the simulation then requires to pass both the network configuration and node name with program instance mapping.

.. warning::
   The node names are used in multiple locations over the various files.
   All the names must match for the simulation to work.

.. note::
   There is no restriction that the program classes must be different per node,
   only the instances need to be different.
   Instead of using different classes it is possible to use a single class and
   set a flag in one of the programs instances that defines its role in the application.

Program Interface
=========================
The largest difference with NetQASM SDK are regarding the interface the programs must adhere to.
The two requirements are that programs have a ``meta`` method that returns a ``ProgramMeta`` object
and that it has a ``run`` method that accepts a ``ProgramContext`` object.

.. code-block:: python
   :caption: squidasm\\sim\\stack\\program.py Program

   class Program(abc.ABC):
       @property
       def meta(self) -> ProgramMeta:
           raise NotImplementedError

       def run(self, context: ProgramContext) -> Dict[str, Any]:
           raise NotImplementedError

The two requirements have strong connection, as the ``ProgramMeta`` object will contain the specification of what the program needs
and the ``ProgramContext`` has the requirements specified earlier.

For example in the code snippet below, the ``csockets=[self.PEER_NAME]``
declaration in ``programMeta`` is required in order for ``csocket = context.csockets[self.PEER_NAME]``
inside the ``run`` method to function. The same is required for the EPR sockets.

.. code-block:: python
   :caption: tutorial_examples\\1_Basics\\application.py AliceProgram

   class AliceProgram(Program):
       PEER_NAME = "Bob"

       @property
       def meta(self) -> ProgramMeta:
           return ProgramMeta(
               name="tutorial_program",
               parameters={},
               csockets=[self.PEER_NAME],
               epr_sockets=[self.PEER_NAME],
               max_qubits=1,
           )

       def run(self, context: ProgramContext):
           # get classical socket to peer
           csocket = context.csockets[self.PEER_NAME]
           # get EPR socket to peer
           epr_socket = context.epr_sockets[self.PEER_NAME]
           # get connection to quantum network processing unit
           connection = context.connection

.. note::
   While currently unsupported, for multi node applications it would be required
   to specify the other node names for the classical and EPR sockets in ``ProgramMeta``.

Output
=======
In order to evaluate the performance of an application,
we would run an application for multiple iterations and possibly multiple parameters and network configurations.
In this section we will show an example of using the ``run_simulation.py`` to evaluate the performance of an application.
To achieve this, we show how to send output from a program to ``run_simulation.py``.

In ``tutorial_examples\3.1_output`` we create an application
that generates EPR pairs, applies a Hadamard gate and measures them:

.. code-block:: python
   :caption: tutorial_examples\\3.1_output\\application.py AliceProgram

   class AliceProgram(Program):
       PEER_NAME = "Bob"

       def __init__(self, num_epr_rounds):
           self._num_epr_rounds = num_epr_rounds

       @property
       def meta(self) -> ProgramMeta:
           return ProgramMeta(
               name="tutorial_program",
               parameters={},
               csockets=[self.PEER_NAME],
               epr_sockets=[self.PEER_NAME],
               max_qubits=2,
           )

       def run(self, context: ProgramContext):
           csocket = context.csockets[self.PEER_NAME]
           epr_socket = context.epr_sockets[self.PEER_NAME]
           connection = context.connection

           # Generate and measure an EPR pair after a Hadamard num_epr_rounds times
           measurements = []
           for _ in range(self._num_epr_rounds):
               qubit = epr_socket.create_keep()[0]
               qubit.H()
               m = qubit.measure()
               measurements.append(m)
               yield from connection.flush()

        # It is recommended to convert output to native python objects to avoid issues
        measurements = [int(r) for r in measurements]
        # Return the measurement results to run_simulation.py
        return {"measurements": measurements}

The program for Bob is identical, except it uses ``recv_keep()`` instead of ``create_keep()``.
The application will run until it has created and measured a number, specified by the argument ``num_epr_rounds``, of EPR pairs.
This parameter is set during the initialization of the program instance.

The program may return a dictionary of various outputs at the end of the program using the ``return`` command.
These dictionaries are returned to the ``run_simulation.py`` file as the return of the ``run(config=cfg, ....)`` command.
In the ``run_simulation.py`` file below we show how we can use the output of the programs
and determine an error rate by comparing what EPR measurements are different.



.. code-block:: python
   :caption: tutorial_examples\\3.1_output\\run_simulation.py

   import numpy as np

   from squidasm.run.stack.config import StackNetworkConfig
   from squidasm.run.stack.run import run
   from application import AliceProgram, BobProgram

   # import network configuration from file
   cfg = StackNetworkConfig.from_file("config.yaml")

   # Set a parameter, the number of epr rounds, for the programs
   epr_rounds = 10
   alice_program = AliceProgram(num_epr_rounds=epr_rounds)
   bob_program = BobProgram(num_epr_rounds=epr_rounds)

   # Run the simulation. Programs argument is a mapping of network node labels to programs to run on that node
   # return from run method are the results per node
   simulation_iterations = 20
   results_alice, results_bob = run(config=cfg,
                                    programs={"Alice": alice_program, "Bob": bob_program},
                                    num_times=simulation_iterations)


   # results have List[Dict[]] structure. List contains the simulation iterations
   results_alice = [results_alice[i]["measurements"] for i in range(simulation_iterations)]
   results_bob = [results_bob[i]["measurements"] for i in range(simulation_iterations)]

   # Create one large list of all EPR measurements
   results_alice = np.concatenate(results_alice).flatten()
   results_bob = np.concatenate(results_bob).flatten()

   # Per EPR determine if results are identical
   errors = [result_alice != result_bob for result_alice, result_bob in zip(results_alice, results_bob)]

   print(f"average error rate: {sum(errors) / len(errors) * 100: .1f}% using {len(errors)} epr requests")
   print(f"average value Alice: {sum(results_alice) / len(results_alice)}")
   print(f"average value Bob: {sum(results_bob) / len(results_bob)}")


For this example, a network configuration was used with a imperfect link.
The fidelity of the link is 0.9.

.. note::
   Before returning the ``measurements`` we convert them to native python integers.
   It is advisable to convert and ``Future`` type object to a native (or numpy) object before any data processing,
   as ``Future`` type objects may cause unexpected behaviour in various operations.


Running this simulation will result give a random result. One possible output is:

.. code-block:: text

   average error rate:  7.0% using 200 epr requests
   average value Alice: 0.515
   average value Bob: 0.525


.. note::
   The return of the run method is of type ``List[List[Dict]]``.
   The first list is ordered per simulation node.
   The second list is ordered using the simulation iteration.
   The dictionary is the dictionary that is returned by the program.

Logging
=============
As more advanced applications are created and tested on networks that simulate noise and loss,
it will become inevitable that in some edge cases,
the application will end return unexpected results or crash.
Using logs help in the process of finding the cause.

To show the usage of logging we use example: ``tutorial_examples\3.2_logging``.
In this example an QKD like application has been created.
The purpose of this application is to send a message of a size that is unknown by the receiving party.
The message and meta data are encrypted via a QKD like encryption.
This encryption is only used as an example and is not secure against attacks.
The application sends the bits one by one, together with a bit that indicates the end of the message.

The following AliceProgram uses logging by moving away from print statements to statements using a logger:

.. code-block:: python
   :caption: tutorial_examples\\3.2_logging\\application.py Alice


   class AliceProgram(Program):
       PEER_NAME = "Bob"

       def __init__(self, message: List[int]):
           self._message = message

       @property
       def meta(self) -> ProgramMeta:
           return ProgramMeta(
               name="alice_program",
               parameters={},
               csockets=[self.PEER_NAME],
               epr_sockets=[self.PEER_NAME],
               max_qubits=2,
           )

       def run(self, context: ProgramContext):
           csocket = context.csockets[self.PEER_NAME]
           epr_socket = context.epr_sockets[self.PEER_NAME]
           connection = context.connection

           logger = LogManager.get_stack_logger("AliceProgram")

           for i, bit in enumerate(self._message):
               logger.debug(f"Start round: {i}")
               if not (bit == 0 or bit == 1):
                   logger.warning(f"Element {i} of message is not 0 or 1")

               # Generate two encryption bits from EPR
               q1, q2 = epr_socket.create_keep(number=2)
               q1.H()
               q2.H()
               m1 = q1.measure()
               m2 = q2.measure()
               yield from connection.flush()
               logger.info(f"Measured qubits: {m1} {m2}")

               # Bit indicating if bob should continue listening, 0 if this is the last bit, else 1
               bit_continue = int(i < len(self._message) - 1)

               # Send encrypted data bit and bit_continue
               bits_to_send = [bit ^ m1, bit_continue ^ m2]
               csocket.send(to_bit_string(bits_to_send))
               logger.info(f"Send bits: {bits_to_send[0]} {bits_to_send[1]}")

           logger.info(f"Finished")
           return {}


The AliceProgram is initialized with the message it must send to Bob.
It loops the program over each bit it is to send.
In each loop iteration it will generate two encryption bits via EPR pairs.
It then sends Bob the message bit and a "continue bit" after performing an XOR with the encryption bits.

There are multiple types of logger methods and these correspond to the 5 levels of logging.
These levels are in order of highest to lowest: critical, error, warning, info and debug.
Messages are logged to a certain level, depending on what logger method was used.

The logger object is obtained via :python:`logger = LogManager.get_stack_logger("AliceProgram")`.
By initializing the logger object with a string, such as: `"AliceProgram"`,
the logger is initialized as a sub-logger of that type.
This sub-logger name will show up in the log messages and
in this case will provide the context that these messages originate from the AliceProgram.

The BobProgram is similar to the AliceProgram.
It obtains the encryption bits via the EPR pairs and can decode the message that Alice has sent.
It uses the "continue bit" received from Alice to decide if it is to continue its loop:

.. code-block:: python
   :caption: tutorial_examples\\3.2_logging\\application.py Bob

   class BobProgram(Program):
       PEER_NAME = "Alice"

       @property
       def meta(self) -> ProgramMeta:
           return ProgramMeta(
               name="bob_program",
               parameters={},
               csockets=[self.PEER_NAME],
               epr_sockets=[self.PEER_NAME],
               max_qubits=2,
           )

       def run(self, context: ProgramContext):
           csocket: Socket = context.csockets[self.PEER_NAME]
           epr_socket: EPRSocket = context.epr_sockets[self.PEER_NAME]
           connection: BaseNetQASMConnection = context.connection

           logger = LogManager.get_stack_logger("BobProgram")

           bit_continue = 1
           received_message = []

           while bit_continue:
               logger.debug(f"Start round: {len(received_message)}")

               # Generate two encryption bits from EPR
               q1, q2 = epr_socket.recv_keep(number=2)
               q1.H()
               q2.H()
               m1 = q1.measure()
               m2 = q2.measure()
               yield from connection.flush()
               logger.info(f"Measured qubits: {m1} {m2}")

               # Receive classical communication
               bits_received = yield from csocket.recv()
               assert isinstance(bits_received, str)
               bits_received = from_bit_string(bits_received)
               logger.info(f"Received bits: {bits_received[0]} {bits_received[1]}")

               # XOR message with encryption bits
               bit = bits_received[0] ^ m1
               bit_continue = bits_received[1] ^ m2

               received_message.append(bit)

           logger.info(f"Finished, message received: {received_message}")
           return {"received message": received_message}


The logger settings are set up in the ``run_simulation.py`` file.
A log level is set using the following command:

.. code-block:: python
   :caption: tutorial_examples\\3.2_logging\\run_simulation.py

   LogManager.set_log_level("INFO")

The log level determines what messages will get logged. Setting the log level to ``DEBUG`` will enable all log messages.
The other levels will disregard messages of a lower level.

By default the logs are sent to terminal, but they can be redirected to a log file using:

.. code-block:: python
   :caption: tutorial_examples\\3.2_logging\\run_simulation.py

   # Disable logging to terminal
   logger = LogManager.get_stack_logger()
   logger.handlers = []
   # Enable logging to file
   LogManager.log_to_file("info.log")

This will result in the logs being written into the ``info.log`` file.

The message that Alice will send is set during the initialization of the program: :python:`AliceProgram(message)`.
After the simulation was run we can compare the message received by Bob with the original message:

.. code-block:: python
   :caption: tutorial_examples\\3.2_logging\\run_simulation.py

   # Create instances of programs to run
   message = [0, 1, 1, 0, 0]
   alice_program = AliceProgram(message)
   bob_program = BobProgram()

   # Run the simulation. Programs argument is a mapping of network node labels to programs to run on that node
   _, bob_results = run(config=cfg,
                        programs={"Alice": alice_program, "Bob": bob_program},
                        num_times=1)

   message_received = bob_results[0]["received message"]
   errors = [int(sent != received) for sent, received in zip(message, message_received)]

   print(f"sent message:     {message}\n"
         f"received message: {message_received}\n"
         f"errors:           {errors}")

Usually this will result in the message being sent over successfully:

.. code-block:: text
   :caption: output

   sent message:     [0, 1, 1, 0, 0]
   received message: [0, 1, 1, 0, 0]
   errors:           [0, 0, 0, 0, 0]

The logs can be found in the ``info.log`` file. In this example it will contain more than 1000 lines,
with an example subsection being:

.. code-block:: text
   :caption: tutorial_examples\\3.2_logging\\info.log

   ...
   ...
   INFO:44000.0 ns:Stack.Netstack(Bob_netstack):waiting for result for pair 1
   INFO:44000.0 ns:Stack.Netstack(Alice_netstack):got result for pair 1: ResCreateAndKeep(create_id=5, directionality_flag=0, sequence_number=5, purpose_id=0, remote_node_id=1, goodness=0.99, bell_state=<BellIndex.B00: 0>, logical_qubit_id=1, time_of_goodness=44000.0)
   INFO:44000.0 ns:Stack.Netstack(Alice_netstack):mapping virtual qubit 1 to physical qubit 1
   INFO:44000.0 ns:Stack.Netstack(Alice_netstack):gen duration (us): 0
   INFO:44000.0 ns:Stack.Netstack(Bob_netstack):got result for pair 1: ResCreateAndKeep(create_id=5, directionality_flag=1, sequence_number=5, purpose_id=0, remote_node_id=0, goodness=0.99, bell_state=<BellIndex.B00: 0>, logical_qubit_id=1, time_of_goodness=44000.0)
   INFO:44000.0 ns:Stack.Netstack(Bob_netstack):mapping virtual qubit 1 to physical qubit 1
   INFO:44000.0 ns:Stack.Netstack(Bob_netstack):gen duration (us): 0
   INFO:44000.0 ns:Stack.GenericProcessor(Alice_processor):
   Finished waiting for array slice @10[R0:R1]
   INFO:44000.0 ns:Stack.GenericProcessor(Bob_processor):
   Finished waiting for array slice @8[R5:R6]
   INFO:66000.0 ns:Stack.AliceProgram:Measured qubits: 0 1
   INFO:66000.0 ns:Stack.AliceProgram:Send bits: 1 0
   ...
   ...

The messages are structured into four segments that are separated using a ``:`` character.
The first segment is the log level. The second is the time at which the message was logged.
This time is the time inside of the simulation, not the real-world, in nano seconds.
The third segment is the sub-logger name, this is determined by the command invoked to retrieve a logger.
For example using: :python:`LogManager.get_stack_logger("AliceProgram")` will result in the text: "AliceProgram" being part of this segment.
The last segment is the message.

Most of the messages inside of the example originate from SquidASM.
The SquidASM messages register events such as NetQASM code being compiled and various NetQASM instructions being executed.

For this example we use an imperfect link with a fidelity of 0.9.
Thus there is a chance that one or more of the EPR pair measurements do not return the same result.
This may result in the following output:

.. code-block:: text
   :caption: output

   sent message:     [0, 1, 1, 0, 0]
   received message: [0, 0]
   errors:           [0, 1]

This behaviour may be unexpected as we might have expected Bob to receive 5 bits.
Investigating the logs in the ``info.log`` file will reveal:

.. code-block:: text
   :caption: tutorial_examples\\3.2_logging\\info.log

   ...
   ...
   INFO:44000.0 ns:Stack.AliceProgram:Measured qubits: 1 0
   INFO:44000.0 ns:Stack.AliceProgram:Send bits: 0 1
   ...
   INFO:44000.0 ns:Stack.BobProgram:Measured qubits: 0 1
   INFO:44000.0 ns:Stack.BobProgram:Received bits: 0 1
   INFO:44000.0 ns:Stack.BobProgram:Finished, message received: [0, 0]

We can observe that in the second step the EPR pair measurement resulted in a different result for both qubits.
Thus an error in the message was introduced, but also the bit indicating if the message end was reached was compromised.
Thus the BobProgram decided too early that it was finished.