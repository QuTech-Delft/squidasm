Usage
=====

To use squidasm do for example


.. code-block:: python

   from squidasm.dummy_module import DummyClass
   dc = DummyClass(4)
   dc.add_to_x(3)
   print(dc.get_x())  # prints 7
