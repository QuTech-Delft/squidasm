.. _label_netqasm:

************************
NetQASM
************************
In this section we go into details of NetQASM and its role for writing applications that can be simulated using SquidASM.
We explain the NetQASMConnection object and the importance of ``connection.flush()`` code.

NetQASM language
=================
NetQASM is an instruction set architecture that allows one to interface with quantum network processing units(QNPU) and run applications on a quantum network.
Its name refers to it being a network(Net) quantum(Q) assembly(ASM) language.
Due to NetQASM being an assembly language it looks similar to classical assembly languages.
Moreover it is also similar to OpenQASM, which is a quantum computing assembly language.
An example of NetQASM code from the `paper introducing NetQASM <https://pure.tudelft.nl/ws/portalfiles/portal/131483787/Dahlberg_2022_Quantum_Sci._Technol._7_035023.pdf>`_:

.. code-block:: text
   :caption: NetQASM code

    array 10 @0                   // array for writing EPR results to
    array 1 @1                    // array with virtual IDs for enangled qubits to be generated
    store 0 @1 [0]                // set virtual ID of the only generated qubit to 0
    array 20 @2                   // array for holding EPR request parameters
    store 0 @2[0]                 // set request type to 0 (Create and Keep)
    store 1 @2 [1]                // set number of requested EPR pairs to 1
    create epr (1,0) 1 2 0        // send command to create EPR pair
    wait_all @0 [0:10]            // wait until results for first pair (10 elements) are available
    set Q0 0
    meas QO MO                    // measure the entangled qubit
    qfree QO
    ret reg MO                    // return measurement outcome

It is not expected from users to directly create NetQASM routines,
as the NetQASM SDK allows one to construct a routine programmatically via python.
This programmatic construction of the routine may cause some confusion,
as on might expect that after executing these commands in a program:

.. literalinclude:: ../../../examples/tutorial/1_Basics/application.py
   :language: python
   :caption: examples/tutorial/1_Basics/application.py AliceProgram
   :pyobject: AliceProgram
   :lines:  26-28

an EPR pair was generated and measured.
This is not the case, the only thing these commands do,
is registering these actions to the "queue" of NetQASM SDK for the current node.
Only once the NetQASM SDK compiles the instructions to NetQASM code and sends that to the QNPU, do these actions occur.
This compilation and sending of the instructions are part of the ``connection.flush()`` command.

The interactions for compiling and sending NetQASM code are done via the ``connection`` object.
The object is called ``connection`` in this tutorial, but is a ``BaseNetQASMConnection`` type object.
The connection component of the name is due the host and QNPU are not being the same device,
so the NetQASMConnection object represents the link and the ability of the host to send instructions to the QNPU.

The compilation of instructions to NetQASM code and the NetQASM code being sent and executed on the QNPU all occurs in the ``connection.flush()`` command.
The NetQASM SDK provides methods that allow us to first compile the NetQASM instructions into a proto subroutine and view the instructions before sending them to the QNPU.
When we replace ``connection.flush()`` in Alice's program with the following code:

.. code-block:: python

   subroutine = connection.compile()
   print(f"Alice's subroutine:\n\n{subroutine}\n")
   yield from connection.commit_subroutine(subroutine)

This changes the example to:

.. literalinclude:: ../../../examples/tutorial/2.1_NetQASM-language/application.py
   :language: python
   :caption: examples/tutorial/2.1_NetQASM-language/application.py
   :pyobject: AliceProgram
   :emphasize-lines:  21-24


The application will run as it did previously, except that we get to view the proto subroutine that Alice sends to the QNPU:

.. code-block:: text

   Subroutine
   NetQASM version: (0, 10)
   App ID: 0
    LN | HLN | CMD
      0    () set R1 10
      1    () array R1 @0
      2    () set R1 1
      3    () array R1 @1
      4    () set R1 0
     ....
     20    () set R8 2
     21    () set R9 0
     22    () create_epr R1 R2 R7 R8 R9
     ....
     44    () jmp 39
     45    () wait_all @0[R3:R5]
     46    () set R1 0
     ....
     56    () set Q0 0
     57    () h Q0
     58    () set Q0 0
     59    () meas Q0 M0
     60    () qfree Q0
     61    () set R1 0
     62    () store M0 @3[R1]
     ....


.. note::

   For a user, it could be that little interaction happens with the ``connection`` object,
   other than the ``connection.flush()`` and initialisation for local qubits ``local_qubit = Qubit(connection)``,
   but the connection is actually the central interaction point for a program.
   When a command on a qubit or epr socket is invokes it wil actually forward these instructions,
   with some id of the object attached, to the ``connection``.
   Thus all these objects have a reference to ``connection`` in their backend and
   why qubit initialization requires the ``connection`` object.

Future objects
===============
An important consequence is that all instructions and thus all results of these instructions have not happened before the subroutine is sent to the QNPU.
Thus the output variable ``result`` of a measure operation does not yet contain the result of the measurement after ``result = qubit.measure()`` has been executed in the python code.
``result`` only has a value after ``yield from connection.flush()`` is executed.

To deal with this situation, the output of ``qubit.measure()`` is a ``netqasm.sdk.future.Future`` object.
These object behave akin to a placeholder or pointer before the flush, but as a normal integer afterwards.
Due to this many operations using a ``Future`` object will cause an error if done before a flush:

.. literalinclude:: ../../../examples/tutorial/2.2_Future-objects/application.py
   :language: python
   :caption: examples/tutorial/2.2_Future-objects/application.py
   :pyobject: AliceProgram
   :emphasize-lines:  17-35

Removing any of the commented out code will result in the following error:

.. code-block:: text

     AttributeError: 'NoneType' object has no attribute 'get_array_part'

As shown in the example above,
using a native python if statement with the result of a measurement before the connection is flushed, is not possible.
More generally using native python ``if``, ``for`` or ``while`` statements do not translate into the NetQASM routine that is sent to a QNPU.

In order to create NetQASM routines with control flow,
special methods in the NetQASM SDK need to be used, such as ``if_eq(a, b, body)`` that is a method of the ``BaseNetQASMConnection`` object.
A `NetQASM tutorial <https://netqasm.readthedocs.io/en/latest/quickstart/using-sdk.html#simple-classical-logic>`_
goes into more detail regarding using such methods.

.. warning::
    The NetQASM language supports many features, such as specifying the measurement basis in a measurement,
    but not all of these features are currently supported in SquidASM.
    It is advisable to be careful when using features not shown in this tutorial.
