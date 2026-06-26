"""Behavior tests for the example block."""

from __future__ import annotations

from scistudio_package_lcms.blocks import ExampleBlock


def test_ports_declared() -> None:
    assert ExampleBlock.input_ports, "block must declare input ports"
    assert ExampleBlock.output_ports, "block must declare output ports"


def test_passthrough_returns_input() -> None:
    # ``process_item`` does not depend on block construction state, so build the
    # instance without running ``__init__`` to keep the test independent of the
    # core block lifecycle.
    block = ExampleBlock.__new__(ExampleBlock)
    sentinel = object()
    assert block.process_item(sentinel, None) is sentinel
