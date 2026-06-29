"""Example processing block.

A minimal Tier-1 block: override ``process_item`` only and let the engine
iterate the input Collection for you (peak memory O(1 item)). See the core
block-development guide (``docs/block-development/block-contract.md``,
``collection-guide.md``) for tiers and the full contract.

Replace the passthrough logic and the ports with your own.
"""

from __future__ import annotations

from typing import Any, ClassVar

from scistudio.blocks.base.config import BlockConfig
from scistudio.blocks.base.ports import InputPort, OutputPort
from scistudio.blocks.process.process_block import ProcessBlock
from scistudio.stability import stable

from scistudio_package_lcms.types import ExampleSeries


@stable(since="0.1.0")
class ExampleBlock(ProcessBlock):
    """Pass each input series through unchanged.

    Ports use the concrete ``ExampleSeries`` type. Concrete accepted types
    drive edge-time connection checks, preview routing, and canvas semantics —
    prefer the most specific applicable ``DataObject`` subclass for every port.
    """

    name: ClassVar[str] = "Example Passthrough"
    description: ClassVar[str] = "Return each input series unchanged."
    version: ClassVar[str] = "0.1.0"
    algorithm: ClassVar[str] = "passthrough"

    input_ports: ClassVar[list[InputPort]] = [
        InputPort(
            name="series",
            accepted_types=[ExampleSeries],
            is_collection=True,
            required=True,
            description="Input series to process.",
        ),
    ]
    output_ports: ClassVar[list[OutputPort]] = [
        OutputPort(
            name="series",
            accepted_types=[ExampleSeries],
            is_collection=True,
            description="Processed series.",
        ),
    ]

    def process_item(self, item: Any, config: BlockConfig) -> Any:
        """Process a single item from the input Collection.

        The engine calls this once per item, handling iteration and memory
        management. Replace the body with your transformation.
        """
        # TODO: replace with your transformation logic.
        return item


__all__ = ["ExampleBlock"]
