# Introduction

`A SKiff` is a python library for typed parsing, creation and modification of KiCad files.

## Features

* Deserialize KiCad files into Python structures and back
* Library aims to introduce zero git diff to untouched file sections
* Even if part of KiCad file is not explicitly supported it should never be dropped from file
* Targets KiCad 10 (backward compatibility with KiCad 8+)

## Documentation Structure

* [Quick start](quick-start.md) describes the installation process and simple usage.
* [Philosophy](philosophy.md) few general remarks about `askiff` API philosophy.
* [API Reference](reference.md) auto generated documentation of library interface.
