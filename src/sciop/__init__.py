from warnings import filterwarnings as _filterwarnings

from sciop._version import __version__

__all__ = [
    "__version__",
]

# annoying pydantic warnings from editable mixin about overriding parent attributes
# even though that's fine to do
# https://github.com/pydantic/pydantic/issues/7009
_filterwarnings(
    action="ignore",
    category=UserWarning,
    module="pydantic",
    message=r".*shadows an attribute in parent.*",
)
