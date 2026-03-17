"""convert humanized strings back to non humanized strings"""

import re

_NUMBER_PATTERN = re.compile(r"(?P<number>[\d,.]*)\s*(?P<suffix>\w*)")


def parse_size(size: str) -> float:
    """
    Parse a humanized size back to an int (bytes).

    Assumes that all sized are base-2 (kibibytes not kilobytes) since that's all we use on here.
    """
    if isinstance(size, int | float):
        return size
    match = _NUMBER_PATTERN.match(size)
    if not match:
        raise ValueError(f"Invalid size {size!r}")
    number = float(match.groupdict()["number"])
    suffix = match.groupdict()["suffix"]
    if not suffix:
        multiplier = 1
    else:
        try:
            multiplier = _prefix_sizes[suffix[0].lower()]
        except KeyError as e:
            raise KeyError(f"Unknown size suffix: {suffix}") from e

    return number * multiplier


_prefix_sizes = {"": 1, "b": 1, "k": 2**10, "m": 2**20, "g": 2**30, "t": 2**40, "p": 2**50}
