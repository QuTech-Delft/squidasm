# Teleportation
Performs a CNOT operation distributed over two nodes: Alice and Bob.
Alice owns the control qubit and Bob the target qubit.

## Inputs
Alice: specification of the control qubit
* `app_alice`:
  * `phi` (float)
  * `theta` (float)

Bob: specification of the target qubit
* `app_bob`: 
  * `phi` (float)
  * `theta` (float)

## Output
Corrections measured by alice (sent to bob) and qubit state (4x4 matrix) at bob after telepotation
* `app_alice`:
  * `epr_meas` (int): Result of Alice's measurement of her EPR qubit
* `app_bob`: 
  * `epr_meas` (int): Result of Bob's measurement of his EPR qubit
