"""Example package-owned data type.

Mirrors the spectroscopy ``Spectrum`` pattern: subclass a core ``DataObject``
type and pin the semantic names through ``__init__`` defaults. Replace this
with your own type — or return an empty list from :func:`get_types` if your
package adds no new types (blocks can operate on core types directly).

This module is the package's **developer-facing reuse surface** (ADR-052 §4.2,
spec §13.1): the type an author imports to name on a port and to build. The
standardized member set a package type satisfies against its own version line:

* ``ExampleSeries`` — public at the package top level, subclasses a core
  ``DataObject`` (``stable``).
* ``ExampleSeries(data=…, meta=…)`` — canonical construction, inherited from
  core; the signature is not redefined (``stable``).
* ``ExampleSeries.Meta`` — typed, frozen metadata schema (``stable``).
* ``ExampleSeries.from_arrays(…)`` — the *MUST-shape* domain-native packing
  constructor **on the type** (never a module-level ``_support`` builder);
  shipped as a skeleton that raises so an unfilled package fails loudly
  (ADR-052 §13.3).
* ``to_memory`` / ``to_pandas`` / ``to_numpy`` / ``sel`` / ``with_meta`` —
  inherited from core and **never shadowed** (the ergonomic accessors stay
  core's, spec §10).
"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict
from scistudio.core.types.series import Series
from scistudio.stability import stable

#: Canonical semantic names for an :class:`ExampleSeries`.
INDEX_NAME = "x"
VALUE_NAME = "value"


@stable(since="0.1.0")
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

    @stable(since="0.1.0")
    class Meta(BaseModel):
        """Per-object typed metadata. Frozen for immutable ``with_meta`` updates."""

        model_config = ConfigDict(frozen=True)

        unit: str | None = None
        source_file: str | None = None

    @classmethod
    @stable(since="0.1.0")
    def from_arrays(
        cls,
        index: Any,
        values: Any,
        *,
        meta: ExampleSeries.Meta | None = None,
    ) -> ExampleSeries:
        """Construct an :class:`ExampleSeries` from domain-native arrays.

        The ADR-052 §13.1 *MUST-shape* member: a domain-native packing
        constructor that lives **on the type** — not a free function and not a
        ``_support`` module builder. It takes the author's natural inputs (here
        an index array and a value array), packs them into the canonical Arrow
        payload, and returns ``cls(data=…, …)`` so callers never touch Arrow
        internals.

        The template ships this as a skeleton that raises, so a package that
        forgets to implement its construction half fails loudly at test/runtime
        rather than shipping a half-contract (ADR-052 §13.3). Replace the body
        with your packing logic and update ``tests/test_contract.py`` to assert
        the real return value.
        """
        raise NotImplementedError(
            "ExampleSeries.from_arrays is an ADR-052 §13.1 contract skeleton; "
            "implement it to pack domain-native arrays into the canonical "
            "data= form and return cls(...)."
        )


@stable(since="0.1.0")
def get_types() -> list[type]:
    """Return the package's exported ``DataObject`` types for ``scistudio.types``."""
    return [ExampleSeries]


__all__ = ["INDEX_NAME", "VALUE_NAME", "ExampleSeries", "get_types"]
