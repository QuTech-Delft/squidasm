# from typing import Any, Callable, Dict, List, Optional, Tuple, Union

# class QuantumErrorModel:
#     pass

# class QuantumMemory:
#     def __init__(
#         self,
#         num_positions: int = ...,
#         models: Optional[Dict] = ...,
#         memory_noise_models: Optional[
#             Union[QuantumErrorModel, List[QuantumErrorModel]]
#         ] = ...,
#         qubit_types: Optional[str] = ...,
#         properties: Optional[Dict] = ...,
#         port_names: Optional[Any] = ...,
#     ) -> None: ...
#     def measure(
#         self,
#         positions: Optional[Union[int, List[int]]] = ...,
#         observable: Any = ...,
#         meas_operators: Any = ...,
#         discard: Any = ...,
#         skip_noise: Any = ...,
#         check_positions: Any = ...,
#     ) -> Tuple[List[int], List[float]]: ...
