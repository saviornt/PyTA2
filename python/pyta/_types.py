"""Internal types shared by the Python API layer."""

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

import numpy as np
from numpy.typing import NDArray

type Float64Array = NDArray[np.float64]

#: Rebuilds the caller's container from a result array and a column label.
type Restore = Callable[[Float64Array, str], Any]


@dataclass(frozen=True, slots=True)
class Prepared:
    """One normalized series plus the means of returning the caller's container."""

    values: Float64Array
    restore: Restore


@dataclass(frozen=True, slots=True)
class PreparedColumns:
    """A multi-column indicator's input, one series per slot in slot order.

    `labels` name each series as error messages should: the caller's column
    name, or its position for unnamed input. `roles` are the roles the series
    were matched to.
    """

    values: tuple[Float64Array, ...]
    labels: tuple[str, ...]
    roles: tuple[str, ...]
    restore: Restore
