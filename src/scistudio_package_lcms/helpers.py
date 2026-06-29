"""Optional public helpers for the package's reuse surface (ADR-052 §4.2).

This is the **SHOULD** placeholder of the developer-facing contract (spec
§13.1, §13.3): an empty public module where a package adds the cross-type or
coerce/validate utilities that make an author's life easier — for example a
``coerce_<domain>(collection)`` normalizer that accepts a ``Collection`` and
returns canonical instances of your type. The more a package exposes,
well-named and documented, the more comfortable its users are.

Rules for anything you add here (enforced by ``scripts/validate_contract.py``
and the surface freeze test):

* It is public — no leading underscore. ``_support``-style internal modules are
  legitimate only for genuinely package-internal code no author should call.
* It carries an ADR-052 §5 stability marker (``@stable`` / ``@provisional``)
  with a ``Since`` against this package's version line.
* It does **not** shadow the inherited ``to_pandas`` / ``to_numpy``; the
  ergonomic accessors stay core's (spec §10).
* It is listed in ``__all__`` below.

Construction and reading belong **on the type** (see
``ExampleSeries.from_arrays`` in ``types.py``); reach for this module only for
utilities that span types or do not belong on a single one.
"""

from __future__ import annotations

__all__: list[str] = []
