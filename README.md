# A SKiff - A Simple KiCad File Flow

Copyright (c) 2026 [Antmicro](https://www.antmicro.com)

Python library for typed parsing, creation and modification of KiCad files.

## Features

* Deserialize KiCad files into Python structures and back
* Library aims to introduce zero git diff to untouched file sections
* Even if part of KiCad file is not explicitly supported it should never be dropped from file
* Targets KiCad 10 (backward compatibility with KiCad 8+)

## Dev guide

### Installation

1. Clone repository
2. Install dependencies & package

```sh
# Inside project repository
uv venv
uv sync --extra dev
```

### Repository structure

* `test_projects/` - directory for projects used for library testing
  * `kicad9/` - synthetic project that aims to include all KiCad features up to version 9
  * `kicad10/` - synthetic project that aims to include all KiCad features up to version 10
  * `jetson-agx-thor-baseboard` - large project, mostly useful for performance testing
* `src/askiff/` - library sourcecode
  * `main.py` - CLI command for library testing
    * run via `uv run askiff -i ${TEST_PROJECT}`
    * loads project files and saves them with no changes
    * useful for:
      * identification of file parts that are not yet supported
      * checking execution time
      * checking formatting correctness (together with `git diff`)
  * `sexpr.py` - handles parsing file to AST (nested list of lists and strings) and writing AST to file
  * `pro.py` - entry point for library usage
    * exposes `AskiffPro` that handles loading and saving of all files in project
  * `auto_serde.py` - offers constructs for automated (de)serialization od structs:
    * `AutoSerde` - base class that offers default, field based (de)serialize function
    * `F` - construct that allows to pass additional data for AutoSerde, usage is similar to dataclasses.field
  * `kicad_structs/` - store definitions of classes matching objects from KiCad files

## Licensing

TODO
