# Introduction

`askiff` is a python library for typed parsing, creation and modification of KiCad files.

askiff provides automatic serialization and deserialization (serde) functionality for KiCad project files, enabling seamless conversion between structured Python data and KiCad's native sexpr formats. It addresses the challenge of working with KiCad's complex, hierarchical file structures by offering typed, field-based (de)serialization that preserves file integrity and supports round-trip editing without unnecessary changes.

The library is designed to handle KiCad 8+ formats, with full support for KiCad 10. It ensures that even unsupported sections of KiCad files remain untouched during processing, maintaining zero git diff for unchanged content. This makes it ideal for automated workflows, file validation, and safe modification of KiCad projects.

## Features

* Deserialize KiCad files into Python structures and back
* Library aims to introduce zero git diff to untouched file sections
* Even if part of KiCad file is not explicitly supported, attempts to preserve it, preventing data loss
* Targets KiCad 10 (backward compatibility with KiCad 8+)
* Simple python abstractions, hiding quirks of KiCad file formats

## Documentation Structure

* [Quick start](quick-start.md) describes the installation process and simple usage.
* [Usage Highlights](usage-highlights.md) few general remarks about `askiff` API philosophy/recommended usage.
* [API Reference](reference.md) auto generated documentation of library interface.
