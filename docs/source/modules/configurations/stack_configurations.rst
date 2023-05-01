Stack Configurations
====================


 .. autoclass:: squidasm.run.stack.config.StackConfig
    :members:
    :undoc-members:
    :member-order: bysource

Generic QDevice
+++++++++++++++++
The generic qdevice implements the following native gates:

* X, Y, Z
* Rot_X, Rot_Y, Rot_Z
* H
* CNOT, CZ

The rotation gates will rotate the qubit around the specified axis with a given angle.

 .. autoclass:: squidasm.run.stack.config.GenericQDeviceConfig
    :members:
    :undoc-members:
    :member-order: bysource

NV QDevice
+++++++++++++++++

The NV qdevice implements the following native gates:

* Rot_X, Rot_Y, Rot_Z
* CXDIR, CYDIR

The CXDIR and CYDIR gates will rotate the target qubit like a Rot_X or Rot_Y gate with a given angle,
but the direction of the rotation is controlled by the control qubit.
Specifically:

.. math::

    CXDIR(\theta) = \ket{0}\bra{0} \otimes Rot\_X(\theta) + \ket{1}\bra{1} \otimes Rot\_X(-\theta)

The topology of the NV qdevice only allows for CXDIR and CYDIR gates between the electron and the carbon qubits.

 .. autoclass:: squidasm.run.stack.config.NVQDeviceConfig
    :members:
    :undoc-members:
    :member-order: bysource