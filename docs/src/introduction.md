# Introduction

`askiff` is a Python library for typed parsing, creation and modification of KiCad files.

askiff provides an automatic serialization and deserialization (serdes) functionality for KiCad project files, enabling seamless conversion between structured Python data and KiCad's native sexpr formats. It addresses the challenge of working with KiCad's complex, hierarchical file structures by offering typed, field-based (de)serialization that preserves file integrity and supports round-trip editing without unnecessary changes.

The library is designed to handle KiCad 8+ formats, with full support for KiCad 10. It ensures that even unsupported sections of KiCad files remain unmodified during processing, maintaining zero git diff for unchanged content. This makes it ideal for automated workflows, file validation, and safe modification of KiCad projects.

## Features

* Deserializing KiCad files into Python structures and back
* No git diff for unmodified file sections
* Preventing data loss in unsupported parts of KiCad files
* Support for KiCad 10 (backward compatibility with KiCad 8+)
* Simple Python abstractions that make it easier to work with complex KiCad file formats

## Documentation Structure

* [Quick start](quick-start.md) describes the installation process and basic usage.
* [Usage highlights](usage-highlights.md) lists general remarks about `askiff` API philosophy and recommended usage.
* [API reference](reference.md) provides an auto generated documentation of the library interfaces.
