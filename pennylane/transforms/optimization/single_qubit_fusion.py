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
"""Transforms for optimizing quantum circuits."""

from pennylane import numpy as np
from pennylane import apply
from pennylane.transforms import qfunc_transform
from pennylane.ops.qubit import Rot
from pennylane.math import allclose, cast_like, stack, zeros

from .optimization_utils import find_next_gate, fuse_rot_angles


@qfunc_transform
def single_qubit_fusion(tape, atol=1e-8, exclude_gates=None):
    """Quantum function transform to fuse together groups of single-qubit
    operations into a general single-qubit unitary operation (:class:`~.Rot`).

    Fusion is performed only between gates that implement the property
    ``single_qubit_rot_angles``. Any sequence of two or more single-qubit gates
    (on the same qubit) with that property defined will be fused into one ``Rot``.

    Args:
        qfunc (function): A quantum function.
        atol (float): An absolute tolerance for which to apply a rotation after
            fusion. After fusion of gates, if the fused angles :math:`\theta` are such that
            :math:`|theta|\leq \text{atol}`, no rotation gate will be applied.
        exclude_gates (None or list[str]): A list of gates that should be excluded
            from full fusion. If set to ``None``, all single-qubit gates that can
            be fused will be fused.

    **Example**

    Consider the following quantum function.

    .. code-block:: python

        def qfunc(r1, r2):
            qml.Hadamard(wires=0)
            qml.Rot(*r1, wires=0)
            qml.Rot(*r2, wires=0)
            qml.RZ(r1[0], wires=0)
            qml.RZ(r2[0], wires=0)
            return qml.expval(qml.PauliX(0))

    The circuit before optimization:

    >>> dev = qml.device('default.qubit', wires=1)
    >>> qnode = qml.QNode(qfunc, dev)
    >>> print(qml.draw(qnode)([0.1, 0.2, 0.3], [0.4, 0.5, 0.6]))
    0: ──H──Rot(0.1, 0.2, 0.3)──Rot(0.4, 0.5, 0.6)──RZ(0.1)──RZ(0.4)──┤ ⟨X⟩

    Full single-qubit gate fusion allows us to collapse this entire sequence into a
    single ``qml.Rot`` rotation gate.

    >>> optimized_qfunc = single_qubit_fusion()(qfunc)
    >>> optimized_qnode = qml.QNode(optimized_qfunc, dev)
    >>> print(qml.draw(optimized_qnode)([0.1, 0.2, 0.3], [0.4, 0.5, 0.6]))
    0: ──Rot(3.57, 2.09, 2.05)──┤ ⟨X⟩

    """
    # Make a working copy of the list to traverse
    list_copy = tape.operations.copy()

    while len(list_copy) > 0:
        current_gate = list_copy[0]

        # If the gate should be excluded, queue it and move on regardless
        # of fusion potential
        if exclude_gates is not None:
            if current_gate.name in exclude_gates:
                apply(current_gate)
                list_copy.pop(0)
                continue

        # Look for single_qubit_rot_angles; if not available, queue and move on.
        # If available, grab the angles and try to fuse.
        try:
            cumulative_angles = stack(current_gate.single_qubit_rot_angles())
        except (NotImplementedError, AttributeError):
            apply(current_gate)
            list_copy.pop(0)
            continue

        # Find the next gate that acts on the same wires
        next_gate_idx = find_next_gate(current_gate.wires, list_copy[1:])

        if next_gate_idx is None:
            apply(current_gate)
            list_copy.pop(0)
            continue

        # Loop as long as a valid next gate exists
        while next_gate_idx is not None:
            # Get the next gate
            next_gate = list_copy[next_gate_idx + 1]

            # Try to merge the angles if next gate is on the same qubit.
            # Only do so if the single_qubit_rot_angles property is implemented.
            if current_gate.wires == next_gate.wires:
                # Check first if the next gate is in the exclusion list
                if exclude_gates is not None:
                    if next_gate.name in exclude_gates:
                        break

                try:
                    next_gate_angles = next_gate.single_qubit_rot_angles()
                except (NotImplementedError, AttributeError):
                    break

                cumulative_angles = fuse_rot_angles(
                    cumulative_angles, cast_like(stack(next_gate_angles), cumulative_angles)
                )
                list_copy.pop(next_gate_idx + 1)
            else:
                break

            next_gate_idx = find_next_gate(current_gate.wires, list_copy[1:])

        # Only apply if the cumulative angle is not close to 0
        if not allclose(cumulative_angles, zeros(3), atol=atol, rtol=0):
            Rot(*cumulative_angles, wires=current_gate.wires)

        # Remove the starting gate from the list
        list_copy.pop(0)

    # Queue the measurements normally
    for m in tape.measurements:
        apply(m)
