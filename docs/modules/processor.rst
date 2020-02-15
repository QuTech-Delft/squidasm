processor
=========

The abstract class :class:`~.processor.NetSquidProcessor` can execute a given (parsed) NetQASM subroutine using NetSquid.
The method :meth:`~.processor.NetSquidProcessor.get_next_subroutine` needs to be overriden to define how the processor should fetch the next subroutine to execute.
By default no quantum operations are actually performed but also needs to be overriden.

The class :class:`~.processor.FromStringNetSquidProcessor` implementes the method :meth:`~.processor.NetSquidProcessor.get_next_subroutine` by simply getting subroutines from a queue of subroutines submitted by :meth:`~.processor.FromStringNetSquidProcessor.put_subroutine`.

.. automodule:: squidasm.processor
   :members:
   :undoc-members:
