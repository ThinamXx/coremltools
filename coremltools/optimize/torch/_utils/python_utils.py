#  Copyright (c) 2023, Apple Inc. All rights reserved.
#
#  Use of this source code is governed by a BSD-3-clause license that can be
#  found in the LICENSE.txt file or at https://opensource.org/licenses/BSD-3-Clause

from typing import Any as _Any


def get_str(val: _Any):
    if isinstance(val, float):
        return f"{val:.5f}"
    return str(val)
