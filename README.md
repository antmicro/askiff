# askiff - A Simple KiCad File Flow

Copyright (c) 2026 [Antmicro](https://www.antmicro.com)

Python library for typed parsing, creation and modification of KiCad files.

askiff provides automatic serialization and deserialization (serde) functionality for KiCad project files, enabling seamless conversion between structured Python data and KiCad's native sexpr formats. It addresses the challenge of working with KiCad's complex, hierarchical file structures by offering typed, field-based (de)serialization that preserves file integrity and supports round-trip editing without unnecessary changes.

The library is designed to handle KiCad 8+ formats, with full support for KiCad 10. It ensures that even unsupported sections of KiCad files remain untouched during processing, maintaining zero git diff for unchanged content. This makes it ideal for automated workflows, file validation, and safe modification of KiCad projects.

## Feature Highlights

* Deserialize KiCad files into Python structures and back
* Library aims to introduce zero git diff to untouched file sections
* Even if part of KiCad file is not explicitly supported, attempts to preserve it, preventing data loss
* Targets KiCad 10 (backward compatibility with KiCad 8+)
* Simple python abstractions, hiding quirks of KiCad file formats

## Installation

```bash
pip install 'git+https://github.com/antmicro/askiff.git'
```

## Quick Start

Typical entry point for operating on a project is `Project`, which handles file discovery, lazy loading necessary files as they are used.

```python
from askiff import Project

# Load a KiCad project
project = Project("path/to/project").load()

# Modify a schematic
project.sch[0].title_block.title = "Modified Title"

# Save the project
project.save()
```

See [documentation]( https://antmicro.github.io/askiff/) for further examples.

## Licensing

TBD
