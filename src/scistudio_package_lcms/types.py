"""Example package-owned data type.

Mirrors the spectroscopy ``Spectrum`` pattern: subclass a core ``DataObject``
type and pin the semantic names through ``__init__`` defaults. Replace this
with your own type — or return an empty list from :func:`get_types` if your
package adds no new types (blocks can operate on core types directly).
"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict
from scistudio.core.types.series import Series

#: Canonical semantic names for an :class:`ExampleSeries`.
INDEX_NAME = "x"
VALUE_NAME = "value"


class ExampleSeries(Series):
    """A minimal 1-D series type owned by this package.

    Subclasses core :class:`~scistudio.core.types.series.Series`. The semantic
    names are pinned via ``__init__`` defaults; replace them with names that
    fit your domain.
    """

    def __init__(
        self,
        *,
        index_name: str | None = INDEX_NAME,
        value_name: str | None = VALUE_NAME,
        length: int | None = None,
        data: Any = None,
        **kwargs: Any,
    ) -> None:
        super().__init__(
            index_name=index_name,
            value_name=value_name,
            length=length,
            data=data,
            **kwargs,
        )

    class Meta(BaseModel):
        """Per-object typed metadata. Frozen for immutable ``with_meta`` updates."""

        model_config = ConfigDict(frozen=True)

        unit: str | None = None
        source_file: str | None = None


def get_types() -> list[type]:
    """Return the package's exported ``DataObject`` types for ``scistudio.types``."""
    return [ExampleSeries]


__all__ = ["INDEX_NAME", "VALUE_NAME", "ExampleSeries", "get_types"]
