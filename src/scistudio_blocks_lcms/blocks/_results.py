"""Build a transient core ``DataFrame`` from a pandas frame.

Shared by the analysis blocks whose output is a *result table* (statistics,
consumption/release rates) rather than a feature table — those return the core
:class:`~scistudio.core.types.DataFrame` directly (no new package type, per the
owner's scope). The framework persists the transient table on auto-flush.
"""

from __future__ import annotations

from typing import Any


def dataframe_from_pandas(frame: Any) -> Any:
    """Pack a pandas frame into a transient core :class:`DataFrame`."""
    import pyarrow as pa
    from scistudio.core.types import DataFrame

    columns = [str(c) for c in frame.columns]
    return DataFrame(
        columns=columns,
        row_count=int(frame.shape[0]),
        schema={c: str(dtype) for c, dtype in zip(columns, frame.dtypes, strict=False)},
        data=pa.Table.from_pandas(frame, preserve_index=False),
    )
