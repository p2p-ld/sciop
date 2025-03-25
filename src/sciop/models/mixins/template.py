"""
Base classes for jinja template handling classes.

See :mod:`.linkml.generators.pydanticgen.template` for example implementation
"""

from copy import copy
from datetime import UTC, datetime
from typing import Any, ClassVar, Dict, List, Optional, Union

import jinja2
from jinja2 import Environment
from pydantic import BaseModel

from sciop.const import TEMPLATE_DIR
from sciop.helpers.type import unwrap_optional

_loader: Optional[jinja2.BaseLoader] = None
_environment: Optional[jinja2.Environment] = None


def get_env_globals() -> dict:
    """
    Jinja environment globals

    Note that starlette's `Jinja2Templates` adds additional globals
    that are not available in e.g. the cli context like `url_for`
    """
    # const within closure to avoid the infinite monkeypatching hell problem
    # since we need to import models here
    from sciop import models

    return {"models": models, "now": datetime.now, "UTC": UTC, "unwrap_optional": unwrap_optional}


def get_env_tests() -> dict:
    return {
        "is_list": lambda x: isinstance(x, list),
    }


def get_loader() -> jinja2.BaseLoader:
    from sciop.config import config

    global _loader
    # hopefully this doesn't need locking,
    # but if you're looking at this code rn because it does in fact need locking,
    # sorry.
    if _loader is None:
        builtin_loader = jinja2.FileSystemLoader(TEMPLATE_DIR)
        if config.template_dir:
            _loader = jinja2.ChoiceLoader(
                [jinja2.FileSystemLoader(config.template_dir), builtin_loader]
            )
        else:
            _loader = builtin_loader
    return _loader


def get_environment() -> Environment:
    global _environment
    if _environment is None:
        _environment = Environment(
            loader=get_loader(),
            autoescape=True,
            trim_blocks=True,
            lstrip_blocks=True,
            optimized=True,
        )
        _environment.globals = get_env_globals()
        _environment.tests = get_env_tests()
    return _environment


class TemplateModel(BaseModel):
    """
    Metaclass to render model results with jinja templates.

    Each subclass needs to declare a :class:`typing.ClassVar` for a
    jinja template within the `templates` directory.

    Templates are written expecting each of the other TemplateModels
    to already be rendered to strings - ie. rather than the ``class.py.jinja``
    template receiving a full :class:`.PydanticAttribute` object or dictionary,
    it receives it having already been rendered to a string. See the :meth:`.render` method.
    """

    template: ClassVar[str]
    _environment: ClassVar[Environment] = get_environment()

    meta_exclude: ClassVar[List[str]] = None

    def render(self, environment: Optional[Environment] = None) -> str:
        """
        Recursively render a template model to a string.

        For each field in the model, recurse through, rendering each :class:`.TemplateModel`
        using the template set in :attr:`.TemplateModel.template` , but preserving the structure
        of lists and dictionaries. Regular :class:`.BaseModel` s are rendered to dictionaries.
        Any other value is passed through unchanged.

        Args:
            environment (:class:`jinja2.Environment`): Template environment
        """
        if environment is None:
            environment = TemplateModel.environment()

        fields = {**self.model_fields, **self.model_computed_fields}

        data = {k: _render(getattr(self, k, None), environment) for k in fields}
        template = environment.get_template(self.template)
        rendered = template.render(**data)
        return rendered

    @classmethod
    def environment(cls) -> Environment:
        """
        Default environment for Template models.
        uses a :class:`jinja2.PackageLoader` for the templates directory within this module
        with the ``trim_blocks`` and ``lstrip_blocks`` parameters set to ``True`` so that the
        default templates could be written in a more readable way.
        """
        return copy(cls._environment)


def _render(
    item: Union[
        TemplateModel, Any, List[Union[Any, TemplateModel]], Dict[str, Union[Any, TemplateModel]]
    ],
    environment: Environment,
) -> Union[Any, list[Any], dict[str, Any]]:
    if isinstance(item, TemplateModel):
        return item.render(environment)
    elif isinstance(item, list):
        return [_render(i, environment) for i in item]
    elif isinstance(item, dict):
        return {k: _render(v, environment) for k, v in item.items()}
    elif isinstance(item, BaseModel):
        fields = {**item.model_fields, **item.model_computed_fields}
        return {k: _render(getattr(item, k, None), environment) for k in fields}
    else:
        return item
