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
"""Utility functions"""
# pylint: disable=import-outside-toplevel
from autograd.numpy.numpy_boxes import ArrayBox
import autoray as ar
from autoray import numpy as np
import numpy as _np

from . import single_dispatch  # pylint:disable=unused-import


def allequal(tensor1, tensor2, **kwargs):
    """Returns True if two tensors are element-wise equal along a given axis.

    This function is equivalent to calling ``np.all(tensor1 == tensor2, **kwargs)``,
    but allows for ``tensor1`` and ``tensor2`` to differ in type.

    Args:
        tensor1 (tensor_like): tensor to compare
        tensor2 (tensor_like): tensor to compare
        **kwargs: Accepts any keyword argument that is accepted by ``np.all``,
            such as ``axis``, ``out``, and ``keepdims``. See the `NumPy documentation
            <https://numpy.org/doc/stable/reference/generated/numpy.all.html>`__ for
            more details.

    Returns:
        ndarray, bool: If ``axis=None``, a logical AND reduction is applied to all elements
        and a boolean will be returned, indicating if all elements evaluate to ``True``. Otherwise,
        a boolean NumPy array will be returned.

    **Example**

    >>> a = torch.tensor([1, 2])
    >>> b = np.array([1, 2])
    >>> allequal(a, b)
    True
    """
    t1 = ar.to_numpy(tensor1)
    t2 = ar.to_numpy(tensor2)
    return np.all(t1 == t2, **kwargs)


def allclose(a, b, rtol=1e-05, atol=1e-08, **kwargs):
    """Wrapper around np.allclose, allowing tensors ``a`` and ``b``
    to differ in type"""
    try:
        # Some frameworks may provide their own allclose implementation.
        # Try and use it if available.
        res = np.allclose(a, b, rtol=rtol, atol=atol, **kwargs)
    except (TypeError, AttributeError):
        # Otherwise, convert the input to NumPy arrays.
        #
        # TODO: replace this with a bespoke, framework agnostic
        # low-level implementation to avoid the NumPy conversion:
        #
        #    np.abs(a - b) <= atol + rtol * np.abs(b)
        #
        t1 = ar.to_numpy(a)
        t2 = ar.to_numpy(b)
        res = np.allclose(t1, t2, rtol=rtol, atol=atol, **kwargs)

    return res


allclose.__doc__ = _np.allclose.__doc__


def cast(tensor, dtype):
    """Casts the given tensor to a new type.

    Args:
        tensor (tensor_like): tensor to cast
        dtype (str, np.dtype): Any supported NumPy dtype representation; this can be
            a string (``"float64"``), a ``np.dtype`` object (``np.dtype("float64")``), or
            a dtype class (``np.float64``). If ``tensor`` is not a NumPy array, the
            **equivalent** dtype in the dispatched framework is used.

    Returns:
        tensor_like: a tensor with the same shape and values as ``tensor`` and the
        same dtype as ``dtype``

    **Example**

    We can use NumPy dtype specifiers:

    >>> x = torch.tensor([1, 2])
    >>> cast(x, np.float64)
    tensor([1., 2.], dtype=torch.float64)

    We can also use strings:

    >>> x = tf.Variable([1, 2])
    >>> cast(x, "complex128")
    <tf.Tensor: shape=(2,), dtype=complex128, numpy=array([1.+0.j, 2.+0.j])>
    """
    if isinstance(tensor, (list, tuple)):
        tensor = np.asarray(tensor)

    if not isinstance(dtype, str):
        try:
            dtype = np.dtype(dtype).name
        except (AttributeError, TypeError):
            dtype = getattr(dtype, "name", dtype)

    return ar.astype(tensor, ar.to_backend_dtype(dtype, like=ar.infer_backend(tensor)))


def cast_like(tensor1, tensor2):
    """Casts a tensor to the same dtype as another.

    Args:
        tensor1 (tensor_like): tensor to cast
        tensor2 (tensor_like): tensor with corresponding dtype to cast to

    Returns:
        tensor_like: a tensor with the same shape and values as ``tensor1`` and the
        same dtype as ``tensor2``

    **Example**

    >>> x = torch.tensor([1, 2])
    >>> y = torch.tensor([3., 4.])
    >>> cast_like(x, y)
    tensor([1., 2.])
    """
    dtype = ar.to_numpy(tensor2).dtype.type
    return cast(tensor1, dtype)


def convert_like(tensor1, tensor2):
    """Convert a tensor to the same type as another.

    Args:
        tensor1 (tensor_like): tensor to convert
        tensor2 (tensor_like): tensor with corresponding type to convert to

    Returns:
        tensor_like: a tensor with the same shape, values, and dtype as ``tensor1`` and the
        same type as ``tensor2``.

    **Example**

    >>> x = np.array([1, 2])
    >>> y = tf.Variable([3, 4])
    >>> convert_like(x, y)
    <tf.Tensor: shape=(2,), dtype=int64, numpy=array([1, 2])>
    """
    interface = get_interface(tensor2)

    if interface == "torch":
        dev = tensor2.device
        return np.asarray(tensor1, device=dev, like=interface)

    return np.asarray(tensor1, like=interface)


def get_interface(tensor):
    """Returns the name of the package that any array/tensor manipulations
    will dispatch to. The returned strings correspond to those used for PennyLane
    :doc:`interfaces </introduction/interfaces>`.

    Args:
        tensor (tensor_like): tensor input

    Returns:
        str: name of the interface

    **Example**

    >>> x = torch.tensor([1., 2.])
    >>> get_interface(x)
    'torch'
    >>> from pennylane import numpy as np
    >>> x = np.array([4, 5], requires_grad=True)
    >>> get_interface(x)
    'autograd'
    """
    namespace = tensor.__class__.__module__.split(".")[0]

    if namespace in ("pennylane", "autograd"):
        return "autograd"

    res = ar.infer_backend(tensor)

    if res == "builtins":
        return "numpy"

    return res


def requires_grad(tensor, interface=None):
    """Returns True if the tensor is considered trainable.

    .. warning::

        The implemetation depends on the contained tensor type, and
        may be context dependent.

        For example, Torch tensors and PennyLane tensors track trainability
        as a property of the tensor itself. TensorFlow, on the other hand,
        only tracks trainability if being watched by a gradient tape.

    Args:
        tensor (tensor_like): input tensor
        interface (str): The name of the interface. Will be determined automatically
            if not provided.

    **Example**

    Calling this function on a PennyLane NumPy array:

    >>> x = np.array([1., 5.], requires_grad=True)
    >>> requires_grad(x)
    True
    >>> x.requires_grad = False
    >>> requires_grad(x)
    False

    PyTorch has similar behaviour.

    With TensorFlow, the output is dependent on whether the tensor
    is currently being watched by a gradient tape:

    >>> x = tf.Variable([0.6, 0.1])
    >>> requires_grad(x)
    False
    >>> with tf.GradientTape() as tape:
    ...     print(requires_grad(x))
    True

    While TensorFlow constants are by default not trainable, they can be
    manually watched by the gradient tape:

    >>> x = tf.constant([0.6, 0.1])
    >>> with tf.GradientTape() as tape:
    ...     print(requires_grad(x))
    False
    >>> with tf.GradientTape() as tape:
    ...     tape.watch([x])
    ...     print(requires_grad(x))
    True
    """
    interface = interface or get_interface(tensor)

    if interface == "tensorflow":
        import tensorflow as tf

        try:
            from tensorflow.python.eager.tape import should_record_backprop
        except ImportError:  # pragma: no cover
            from tensorflow.python.eager.tape import should_record as should_record_backprop

        return should_record_backprop([tf.convert_to_tensor(tensor)])

    if interface == "autograd":
        if isinstance(tensor, ArrayBox):
            return True

        # Currently, in the Autograd interface, we assume
        # that all objects are differentiable by default.
        return getattr(tensor, "requires_grad", True)

    if interface == "torch":
        return getattr(tensor, "requires_grad", False)

    if interface == "numpy":
        return False

    if interface == "jax":
        import jax

        return isinstance(tensor, jax.interpreters.ad.JVPTracer)

    raise ValueError(f"Argument {tensor} is an unknown object")
