# Copyright 2018-2021 Xanadu Quantum Technologies Inc.

# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at

#     http://www.apache.org/licenses/LICENSE-2.0

# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
"""
Contains the Grover Operation template.
"""
import pennylane as qml
from pennylane.operation import AnyWires, Operation
from pennylane.ops import Hadamard, PauliZ, MultiControlledX


class GroverOperator(Operation):
    r"""Performs the Grover Diffusion Operator.

    .. math::

        G = 2 |s \rangle \langle s | - I
        = H^{\bigotimes n} \left( 2 |0\rangle \langle 0| - I \right) H^{\bigotimes n}

    where :math:`n` is the number of wires and :math:`|s\rangle` is the uniform superposition:

    .. math::

        |s\rangle = H^{\bigotimes n} |0\rangle =  \frac{1}{\sqrt{2**n}} \sum_{i=0}^{n} | i \rangle

    For this template, the operator is implemented with a layer of Hadamards, an
    effective multi-controlled Z gate, and another layer of Hadamards.

    .. figure:: ../../_static/templates/subroutines/grover.svg
        :align: center
        :width: 60%
        :target: javascript:void(0);

    This decomposition for the circuit is equivalent to:

    .. figure:: ../../_static/templates/subroutines/grover2.svg
        :align: center
        :width: 60%
        :target: javascript:void(0);

    Args:
        wires (Union[Wires, Sequence[int], or int]): the wires to apply to
        work_wires (Union[Wires, Sequence[int], or int]): optional auxiliary wires to assist
            in the decomposition of :class:`~.ops.qubit.MultiControlledX`.

    **Example**

    For this example, we will be using three wires and ``"default.qubit"``:

    .. code-block:: python

        n_wires = 3
        wires = list(range(n_wires))
        dev = qml.device('default.qubit', wires=wires)

    The Grover Diffusion Operator amplifies the magnitude of the basis state with
    a negative phase.  For example, if the solution to the search problem is the :math:`|111\rangle`
    state, we require an oracle that flips its phase; this could be implemented using a `CCZ` gate:

    .. code-block:: python

        def oracle():
            qml.Hadamard(wires[-1])
            qml.Toffoli(wires=wires)
            qml.Hadamard(wires[-1])

    We can then implement the entire Grover Search Algorithm for ``n`` iterations by alternating calls to the oracle and the diffusion operator:

    .. code-block:: python

        @qml.qnode(dev)
        def GroverSearch(num_iterations=1):
            for wire in wires:
                qml.Hadamard(wire)

            for _ in range(num_iterations):
                oracle()
                qml.templates.GroverOperator(wires=wires)
            return qml.probs(wires)

    >>> GroverSearch(num_iterations=1)
    tensor([0.03125, 0.03125, 0.03125, 0.03125, 0.03125, 0.03125, 0.03125,
            0.78125], requires_grad=True)
    >>> GroverSearch(num_iterations=2)
    tensor([0.0078125, 0.0078125, 0.0078125, 0.0078125, 0.0078125, 0.0078125,
        0.0078125, 0.9453125], requires_grad=True)

    We can see that the marked :math:`|111\rangle` state has the greatest probability amplitude.

    Optimally, the oracle-operator pairing should be repeated :math:`\frac{\pi}{4}\sqrt{2^{n}}$ times.

    """
    num_params = 0
    num_wires = AnyWires
    par_domain = None

    def __init__(self, wires=None, work_wires=None, do_queue=True, id=None):
        self.work_wires = work_wires
        super().__init__(wires=wires, do_queue=do_queue, id=id)

    def expand(self):
        ctrl_str = "0" * (len(self.wires) - 1)

        with qml.tape.QuantumTape() as tape:
            for wire in self.wires[:-1]:
                Hadamard(wire)

            PauliZ(self.wires[-1])
            MultiControlledX(
                control_values=ctrl_str,
                control_wires=self.wires[:-1],
                wires=self.wires[-1],
                work_wires=self.work_wires,
            )
            PauliZ(self.wires[-1])

            for wire in self.wires[:-1]:
                Hadamard(wire)

        return tape