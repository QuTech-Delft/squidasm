from functools import wraps
from typing import Any, List, Tuple

import netsquid as ns
from netsquid_netbuilder.modules.scheduler.interface import IScheduleProtocol


def get_argument(args: tuple, kwargs: dict, position: int, name: str) -> Any:
    """Retrieves an argument from a args kwargs combination of a function call.
    :param args: The tuple of args of the function call
    :param kwargs: The dictionary of kwargs of the function call
    :param position: Position of the argument in the function
    :param name: Name of the argument in the function
    :return:
    """
    if name in kwargs.keys():
        return kwargs[name]
    else:
        return args[position]


def collect_schedule_events(scheduler: IScheduleProtocol) -> dict:
    """
    Modifies the scheduler such that it writes out calls to open and close a link and incoming requests,
     results and errors to a dictionary.

    :param scheduler: The scheduler that will be modified
    :return: The dictionary with lists for the calls to _open_link, _close_link, register_request, register_result and
    register_error functions of the scheduler.
    The items in the list are dictionaries with the argument keyword and value for the call
     combined with simulation time of the call under the 'time' key
    """
    output_dict = {"open": [], "close": [], "request": [], "result": [], "error": []}

    def collect_wrapper(func, event_type: str, method_args: List[Tuple[int, str]]):
        @wraps(func)
        def collect(*args, **kwargs):
            output_item = {"time": ns.sim_time()}
            for arg_position, arg_key in method_args:
                value = get_argument(args, kwargs, arg_position, arg_key)
                output_item[arg_key] = value
            output_dict[event_type].append(output_item)
            return func(*args, **kwargs)

        return collect

    scheduler._open_link = collect_wrapper(
        scheduler._open_link, "open", method_args=[(0, "node1_name"), (1, "node2_name")]
    )
    scheduler._close_link = collect_wrapper(
        scheduler._close_link,
        "close",
        method_args=[(0, "node1_name"), (1, "node2_name")],
    )
    scheduler.register_request = collect_wrapper(
        scheduler.register_request,
        "request",
        method_args=[(0, "node_id"), (1, "req"), (2, "create_id")],
    )
    scheduler.register_result = collect_wrapper(
        scheduler.register_result, "result", method_args=[(0, "node_id"), (1, "res")]
    )
    scheduler.register_error = collect_wrapper(
        scheduler.register_error, "error", method_args=[(0, "node_id"), (1, "error")]
    )

    return output_dict
