#
# Copyright (c) 2017, Stephanie Wehner and Axel Dahlberg
# All rights reserved.
#
# Redistribution and use in source and binary forms, with or without
# modification, are permitted provided that the following conditions are met:
# 1. Redistributions of source code must retain the above copyright
#    notice, this list of conditions and the following disclaimer.
# 2. Redistributions in binary form must reproduce the above copyright
#    notice, this list of conditions and the following disclaimer in the
#    documentation and/or other materials provided with the distribution.
# 3. All advertising materials mentioning features or use of this software
#    must display the following acknowledgement:
#    This product includes software developed by Stephanie Wehner, QuTech.
# 4. Neither the name of the QuTech organization nor the
#    names of its contributors may be used to endorse or promote products
#    derived from this software without specific prior written permission.
#
# THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDER ''AS IS'' AND ANY
# EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE IMPLIED
# WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE ARE
# DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT HOLDER BE LIABLE FOR ANY
# DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR CONSEQUENTIAL DAMAGES
# (INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR SERVICES;
# LOSS OF USE, DATA, OR PROFITS; OR BUSINESS INTERRUPTION) HOWEVER CAUSED AND
# ON ANY THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT LIABILITY, OR TORT
# (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY OUT OF THE USE OF THIS
# SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.

# from SimulaQron.general.hostConfig import *
# from SimulaQron.cqc.backend.cqcHeader import *
# from SimulaQron.cqc.pythonLib.cqc import *
# from SimulaQron.toolbox.measurements import parity_meas

from time import sleep

from squidasm.sdk import NetSquidConnection as CQCConnection
from measurements import parity_meas

import random


#####################################################################################################
#
# main
#
def main():

    # Initialize the connection
    with CQCConnection("Alice") as Alice:

        # Wait a little for recv rules to be installed
        sleep(0.1)

        # Create EPR pairs
        q1 = Alice.createEPR("Bob")[0]
        q2 = Alice.createEPR("Bob")[0]

        # TODO
        Alice.flush()

        # Make sure we order the qubits consistently with Bob
        # Get entanglement IDs
        q1_ID = q1.entanglement_info.sequence_number
        q2_ID = q2.entanglement_info.sequence_number
        # q1_ID = 0
        # q2_ID = 1

        if q1_ID < q2_ID:
            qa = q1
            qc = q2
        else:
            qa = q2
            qc = q1

        # Get the row
        row = random.randint(0, 2)

        # Perform the three measurements
        if row == 0:
            m0 = parity_meas([qa, qc], "XI", Alice)
            m1 = parity_meas([qa, qc], "XX", Alice)
            m2 = parity_meas([qa, qc], "IX", Alice)
        elif row == 1:
            m0 = parity_meas([qa, qc], "XZ", Alice, negative=True)
            m1 = parity_meas([qa, qc], "YY", Alice)
            m2 = parity_meas([qa, qc], "ZX", Alice, negative=True)
        elif row == 2:
            m0 = parity_meas([qa, qc], "IZ", Alice)
            m1 = parity_meas([qa, qc], "ZZ", Alice)
            m2 = parity_meas([qa, qc], "ZI", Alice)
        else:
            raise ValueError(f"Not a row in the square {row}")

    to_print = "\n\n"
    to_print += "==========================\n"
    to_print += f"App Alice: row is:\n"
    for _ in range(row):
        to_print += "(___)\n"
    to_print += f"({m0}{m1}{m2})\n"
    for _ in range(2-row):
        to_print += "(___)\n"
    to_print += "==========================\n"
    to_print += "\n\n"
    print(to_print)


##################################################################################################
if __name__ == "__main__":
    main()
