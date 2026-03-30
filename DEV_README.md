# Dev guide

## Installation

1. Clone repository
2. Install dependencies & package

```sh
# Inside project repository
uv venv
uv sync --extra dev
```

## Repository structure

* `src/askiff/` - library sourcecode
  * `_auto_serde/` - offers constructs for automated (de)serialization of structures:
    * `AutoSerde` - base class that offers default, field based (de)serialize function
    * `F` - construct that allows to pass additional data for AutoSerde, usage is similar to dataclasses.field
      * Passes (de)serialization hints during class initialization, `AutoSerde` replaces them with default field value after class initialized
  * `_cli.py` - CLI command for library testing
    * run via `uv run askiff -i ${TEST_PROJECT_DIR}`
    * loads all project files and saves them with no changes
    * useful for:
      * identification of file parts that are not yet supported
      * checking execution time
      * checking kicad file formatting correctness (together with `git diff`)
  * `pro.py` - entry point for library usage
    * exposes `AskiffPro` that handles loading and saving of all files in project
  * `_sexpr.py` - handles parsing file to AST (nested list of lists and strings) and writing AST to file
  * `board.py, common.py, ...` - store definitions of classes matching objects from KiCad files
* `test_projects/` - directory for projects used for library testing
  * `kicad9/` - synthetic project that aims to include all KiCad features up to version 9
  * `kicad10/` - synthetic project that aims to include all KiCad features up to version 10
  * `jetson-agx-thor-baseboard` - large project, mostly useful for performance testing
