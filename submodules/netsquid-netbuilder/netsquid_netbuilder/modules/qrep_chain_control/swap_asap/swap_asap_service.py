from abc import abstractmethod, ABCMeta

from dataclasses import dataclass
from netsquid.protocols.serviceprotocol import ServiceProtocol


@dataclass
class ReqSwapASAP:
    """Request to generate entanglement with two neighbors and perform entanglement swapping immediately after.

    The request specifies how often the procedure should be repeated, and the maximum amount of time entanglement
    is stored. Note that if entanglement is discarded, or entanglement swapping fails, this does not count towards
    the number of times swap ASAP is performed. Only entanglement swaps with a successful outcome do.
    Specifying the neighbours that entanglement should be generated with is not needed in this request,
    since we assume the repeater node is an automated node that is part of a dedicated repeater chain between
    two end nodes.

    """
    upstream_node_name: str
    downstream_node_name: str
    request_id: int = 0  # Used to match responses to specific requests
    num: int = 0  # Number of times entanglement generation + swap should be performed successfully.

    # If 0, swap ASAP will be repeated until a `ReqSwapASAPAbort` request is received.
    cutoff_time: float = 0  # Entanglement that is stored for this amount of time will be discarded.
    # If 0, cutoff time is not implemented.


@dataclass
class ReqSwapASAPAbort:
    """Stop entanglement generation and swapping. Discards any already generated entanglement."""
    request_id: int or None = None  # request_id of the `ReqSwapASAP` request that needs to be aborted.
    # If request_id is None, all requests are aborted.


@dataclass
class ResSwapASAPFinished:
    """Response to notify the completion of swap ASAP operation corresponding to a specific request.

    Note that completion can either occur because the prespecified maximum number of successful swaps have been
    performed, or because a `ReqSwapASAPAbort` request has been received.

    """
    swap_bell_indices: list  # List of :class:`netsquid.qubits.ketstates.BellIndex`, outcomes of successful swaps.
    downstream_bell_indices: list  # List of :class:`netsquid.qubits.ketstates.BellIndex`,
    # indicating which Bell states were shared with the downstream neighbour.
    upstream_bell_indices: list  # List of :class:`netsquid.qubits.ketstates.BellIndex`,
    # indicating which Bell states were shared with the downstream neighbour.
    goodness: list  # List of 'goodness' parameters that can be used by end nodes to estimate entanglement quality.
    request_id: int = 0  # request_id of the `ReqSwapASAP` request that has now been fulfilled.


@dataclass
class ResSwapASAPError:
    """Response to notify to occurance of an error when handling a request."""
    request_id: int = 0  # request_id of the request that has triggered an error.
    error_code: int = 0  # Can be used to identify the error that occurred.
    # TODO: define error codes using an enum


class SwapASAPService(ServiceProtocol, metaclass=ABCMeta):
    """Service for quantum repeater nodes which are part of a repeater chain utilizing the swap ASAP strategy.

    This service is responsible for generating entanglement with the neighbours of the node (which should be
    well-defined, since it is assumed the node is an automated node that is part of a dedicated repeater chain),
    and consequently swapping it as soon as possible.

    Parameters
    ----------
    node : :class:`~netsquid.nodes.node.Node`
        The node this protocol is running on.
    name : str, optional
        The name of this protocol.

    """

    def __init__(self, node, name=None):
        super().__init__(node=node, name=name)
        self.register_request(req_type=ReqSwapASAP, handler=self.swap_asap)
        self.register_request(req_type=ReqSwapASAPAbort, handler=self.abort)
        self.register_response(res_type=ResSwapASAPFinished)
        self.register_response(res_type=ResSwapASAPError)

    @abstractmethod
    def swap_asap(self, req):
        """Start generating entanglement with both neighbours, and perform entanglement swap when successful.

        This is repeated until either the predefined number of successful swaps has been achieved, or the operation
        is aborted by :meth:`~SwapASAPService.abort`

        Parameters
        ----------
        req : :obj:`ReqSwapASAP`
            Request that needs to be handled by this method.

        Note
        ----
        Should call self.send_response(res).
        When finished successfully, res should be :obj:`ResSwapASAPFinished`.
        If an error occurred, res should be :object:`ResSwapASAPError`.

        """
        assert isinstance(req, ReqSwapASAP)

    @abstractmethod
    def abort(self, req):
        """Abort ongoing swap-ASAP operation.

        Parameters
        ----------
        req : :obj:`ReqSwapASAPAbort`
            Request that needs to be handled by this method.

        """
        assert isinstance(req, ReqSwapASAPAbort)

    def send_response(self, response, name=None):
        """Send a response via a signal, and check if it has the proper format.

        Parameters
        ----------
        response : :class:`collections.namedtuple` or object
            The response instance.
        name : str or None, optional
            The identifier used for this response.
            Default :meth:`~netsquid.protocols.serviceprotocol.ServiceProtocol.get_name` of the request.

        Raises
        ------
        ServiceError
            If the name doesn't match to the request type.

        Note
        ----
        If the response is a :obj:`ResSwapASAPFinished` and the lists of Bell indices for the upstream link, downstream
        link and entanglement swap don't have the same length,
        an error response :obj:`ResSwapASAPError` is sent instead.
        This is because every cycle of the swap-ASAP protocol should yield one Bell index for the downstream link,
        one for the upstream link, and one for the entanglement swap. Thus, if one of the lists is longer than another,
        something must have gone wrong.

        """
        if isinstance(response, ResSwapASAPFinished):
            # Check if upstream link, downstream link and entanglement swap have same number of Bell indices.
            if len(response.swap_bell_indices) != len(response.downstream_bell_indices) \
                    or len(response.swap_bell_indices) != len(response.upstream_bell_indices) \
                    or len(response.swap_bell_indices) != len(response.goodness):
                return self.send_response(response=ResSwapASAPError(request_id=response.request_id,
                                                                    error_code=1))  # TODO determine proper error code
        return super().send_response(response=response, name=name)
