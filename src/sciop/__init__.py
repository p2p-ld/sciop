from importlib.metadata import version
from warnings import filterwarnings as _filterwarnings

from sciop.config import get_config

__version__ = version("sciop")

__all__ = [
    "__version__",
    "get_config",
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
# now sqlmodel has chosen to adopt the behavior too
_filterwarnings(
    action="ignore",
    category=UserWarning,
    module="sqlmodel",
    message=r".*shadows an attribute in parent.*",
)
