#  Copyright (c) 2021, Apple Inc. All rights reserved.
#
#  Use of this source code is governed by a BSD-3-clause license that can be
#  found in the LICENSE.txt file or at https://opensource.org/licenses/BSD-3-Clause

from typing import List

import numpy as np

from coremltools.converters.mil.mil import Block, Operation, Var
from coremltools.converters.mil.mil.passes.graph_pass import AbstractGraphPass

class classproperty(property):
    """
    A decorator class that allow us to have a class-level property
    """
    def __get__(self, owner, cls):
        return self.fget(cls)

def block_context_manager(func):
    """
    This decorator executes a function under the context manager `with block`.
    For instance, given a function `func` with an input block and other arguments:

    def func(block, *args):
        ...
        with block:
            op_1 = mb.add(...)
        ...
        with block:
            op_2 = mb.relu...()

    It can be be streamlined as:

    @block_context_manager
    def func(block, *args):
        ...
        op_1 = mb.add(...)
        ...
        op_2 = mb.relu...()

    Note that, the first argument of the function must have type Block.
    It is highly recommended to decorate a function with block_context_manager if it is calling `with block` multiple times,
    since when the code exit `block`, an expensive _propagate_nonreplaceable_vars() is invoked.
    The decorator reduces the amount of calling `with block` overally.
    """
    def wrapper(*args):
        # Make it compatible with class method.
        if isinstance(args[0], AbstractGraphPass):
            block = args[1]
        else:
            block = args[0]

        if not isinstance(block, Block):
            raise ValueError(
                "The function decorated with block_context_manager must have a Block "
                "type argument as the first input."
            )
        with block:
            return func(*args)
    return wrapper


def _check_child_op_type(op, child_op_type):
    """
    :param op: operation
    :param child_op_type: str
    :return: Return True if op has 1 child and type of that child matches child_op_type
    """
    if len(op.outputs) != 1:
        return False
    child_ops = list(op.outputs[0].child_ops)
    if len(child_ops) != 1:
        return False
    if child_ops[0].op_type == child_op_type:
        return True
    return False


def _check_no_output_connection(block: Block, ops: List[Operation]) -> bool:
    """
    Check that none of the op in this pattern is connected to the output
    (except the last op)

    :param block: Block
    :param ops: List of operations to check on.
    """
    for op in ops[:-1]:
        for out in op.outputs:
            if out in block.outputs:
                return False
    return True


def _check_var_scalar_value_in_interval(x, lower_bound, upper_bound):
    """
    :param x: var
    :param lower_bound: a scalar value
    :param upper_bound: a scalar value
    :return: True if the value of var is in the interval [lower_bound, upper_bound]
    """
    if x.val is None:
        return False
    if not isinstance(x.val, (np.ndarray, np.generic)):
        return False

    if isinstance(x.val, np.ndarray):
        if x.val.size != 1:
            return False
        x_val = x.val[:][0] if len(x.val.shape) > 0 else x.val[()]
    else:
        x_val = x.val

    if x_val >= lower_bound and x_val <= upper_bound:
        return True
    return False


def _check_var_scalar_value(x, val, tol=1e-3):
    """
    :param x: var
    :param val: a scalar value
    :return: True if x.val is equal to val otherwise return False
    """
    if x.val is None:
        return False
    if not isinstance(x.val, np.ndarray) and not np.isscalar(x.val):
        return False

    if isinstance(x.val, np.ndarray):
        if x.val.size != 1:
            return False
        if len(x.val.shape) == 0:
            x_val = x.val
        else:
            x_val = x.val[:][0] if len(x.val.shape) > 0 else x.val[()]
    else:
        x_val = x.val

    if abs(x_val - val) < tol:
        return True
    return False

def _are_ops_identical(op1, op2):
    '''
    Return True, if all inputs of op1 and op2 are identical.
    non-constant inputs must refer to the same object, and constant inputs must have the same value
    '''

    def _are_values_identical(val1, val2):
        np_arr1 = np.array(val1)
        np_arr2 = np.array(val2)
        return np.array_equal(np_arr1, np_arr2)

    def _are_vars_identical(var1, var2):
        if var1.val is None and var2.val is None:
            if var1 != var2:
                return False
        elif var1.val is not None and var2.val is not None:
            if var1.dtype != var2.dtype:
                return False
            if not _are_values_identical(var1.val, var2.val):
                return False
        else:
            return False
        return True

    if op1 == op2:
        return True
    if op1.op_type != op2.op_type:
        return False
    if len(op1.inputs) != len(op2.inputs):
        return False

    for key, value1 in op1.inputs.items():
        if key not in op2.inputs:
            return False
        value2 = op2.inputs[key]
        if isinstance(value1, Var) and isinstance(value2, Var):
            if not _are_vars_identical(value1, value2):
                return False
        elif isinstance(value1, (list, tuple)) and isinstance(value2, (list, tuple)):
            if len(value1) != len(value2):
                return False
            else:
                for i, v in enumerate(value1):
                    if not _are_vars_identical(v, value2[i]):
                        return False
        else:
            return False

    assert len(op1.blocks) == 0, "this method does not handle ops that have blocks in it"
    assert len(op2.blocks) == 0, "this method does not handle ops that have blocks in it"
    return True
