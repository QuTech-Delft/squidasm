from time import sleep

import netsquid as ns
from pydynaa import Entity, EventType, EventExpression


def as_completed(futures):
    futures = list(futures)
    while len(futures) > 0:
        for i, future in enumerate(futures):
            if future.ready():
                futures.pop(i)
                yield future
        sleep(0.1)


class Sleeper(Entity):
    def __init__(self, sleep_ns=1, sleep_real=0.1):
        """Class that can be used to sleep a little to wait for an external (event)
        , i.e. not from NetSquid.

        Example
        -------
        Here the we define a Protocol that wait for something to happen by calling
        the method `has_thing` which might for example wait for some external event.
        >>> class WaitProtocol(Protocol):
        >>>     def __init__(self):
        >>>         self._sleeper = Sleeper()
        >>>
        >>>     def run():
        >>>         while True:
        >>>             if self.has_thing():
        >>>                 break
        >>>             else:
        >>>                 yield self._sleeper().sleep()
        """
        self._event = EventType("LOOP", "event for waiting without blocking netsquid")

    def sleep(self, sleep_ns=1, sleep_real=0.1):
        """Sleep in netsquid and real time.

        This function returns a :class:`pydynaa.EventExpression` which can be yielded on.

        Parameters
        ----------
        sleep_ns : int or float, optional
            How long to sleep (ns) in NetSquid if there is no event on the current timeline.
        sleep_real : int or float, optional
            How long to sleep (s) in real time if there is not event on the current timeline.
        """
        # Check if there are any events on the timeline
        if ns.sim_count_events() == 0:
            # There are no events, so schedule one and wait a little
            # TODO should we wait as long in netsquid as in real time?
            self._schedule_after(sleep_ns, self._event)
            sleep(sleep_real)
            event_expr = EventExpression(source=self, event_type=self._event)
        else:
            # There are events on the timeline so simply wait for the next one
            event_expr = EventExpression()
        return event_expr
