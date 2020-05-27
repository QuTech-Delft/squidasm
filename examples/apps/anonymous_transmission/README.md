# Anonymous transmission
## Inputs TODO
Specification of what qubit to teleport from alice
* `app_alice`:
  * `phi` (float)
  * `theta` (float)
* `app_bob`: null

## Output TODO
Corrections measured by alice (sent to bob) and qubit state (4x4 matrix) at bob after telepotation
* `app_alice`:
  * `m1` (int)
  * `m2` (int)
* `app_bob`:
  * `state`: (List[List[complex]])
    example: `[[0.5, -0.5j], [0.5j, 0.5]]`
* `backend`: null
