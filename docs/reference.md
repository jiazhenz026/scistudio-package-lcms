# API Reference

Generated from docstrings and the `scistudio.stability` decorators by
mkdocstrings + griffe (ADR-052 §7), version-stamped to this package's release.
This is the **developer-facing reuse surface** (ADR-052 §4.2, §13.1): the types,
their constructors, and the public helpers an author imports. Block and
previewer classes are the registration surface, not author API, so they are not
in this reference.

<!-- TODO(#1817): render the ADR-052 §5 tier / Since as a per-symbol badge via a
     griffe extension that reads __scistudio_stability__, and host multiple
     versions side by side (mike), once the core generated-reference toolchain
     lands. Out of scope for the minimal parity build per ADR-052 §7.
     Followup: https://github.com/jiazhenz026/SciStudio/issues/1817 -->

## Package root

::: scistudio_package_lcms
    options:
      show_root_heading: true
      members:
        - get_block_package
        - get_blocks
        - get_package_info
        - get_types
        - get_previewers
        - describe_public_api

## Types

::: scistudio_package_lcms.types
    options:
      show_root_heading: true

## Helpers

::: scistudio_package_lcms.helpers
    options:
      show_root_heading: true
