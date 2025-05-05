import re
from collections.abc import MutableMapping
from typing import TypeVar

T = TypeVar("T", bound=MutableMapping)


def flatten_dict(val: MutableMapping, parent_key: str = "") -> dict:
    """
    Flatten a nested dictionary

    ```python
    {
        "a": 1,
        "b": {
            "c": 2,
            "d.e": 3
        }
    }
    ```

    becomes

    ```python
    {
        "a": 1,
        "b.c": 2,
        "b.d\\.e": 3,
    }
    ```
    """
    items = []
    for key, value in val.items():
        key = str(key)
        key = key.replace(".", "\\.")
        new_key = parent_key + "." + key if parent_key else key
        if isinstance(value, MutableMapping):
            items.extend(flatten_dict(value, new_key).items())
        else:
            items.append((new_key, value))
    return dict(items)


def unflatten_dict(val: dict) -> dict:
    """
    Inverse of :func:`flatten_dict`
    """
    res = {}
    for key, value in val.items():
        parts = re.split(r"(?<!\\)\.", key)
        sub_res = res
        for part in parts[:-1]:
            part = re.sub(r"\\\.", ".", part)
            if part not in sub_res:
                sub_res[part] = dict()
            sub_res = sub_res[part]
        sub_res[re.sub(r"\\\.", ".", parts[-1])] = value
    return res


def merge_dicts(a: T, b: MutableMapping) -> T:
    """
    Update a with values from b, recursively

    References:
        https://stackoverflow.com/a/7205107/13113166
    """
    for key in b:
        if key in a and isinstance(a[key], MutableMapping) and isinstance(b[key], MutableMapping):
            merge_dicts(a[key], b[key])
        else:
            a[key] = b[key]
    return a
