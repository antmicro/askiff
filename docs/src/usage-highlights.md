# Usage highlights

## Typing oriented

The askiff library is built around a Python static typing system (type annotations) and dataclasses.
To ensure correct serialization, it is necessary to ensure type correctness when assigning to objects/fields defined in this library.
The most robust way and one strongly recommended is to use type checkers (e.g. mypy, ty, ...).
Assigning an incorrect type object is likely to lead to runtime exceptions or corrupted files.

## KiCad file structure mirroring

Most classes and their fields directly mirror the structure/map to objects in KiCad files.

The `final` typed fields or the `_askiff_key` field match the keyword used in KiCad files and should never be changed.
If it is necessary to change them, other, related classes should probably be used.
From the Python interface perspective, they are irrelevant.

## Enum based values

KiCad files use multiple keywords and constant values to indicate object subtypes or some setting values.

To reduce the risk of spelling errors and make usage more clear, `askiff` abstracts this using 3 methods.
It is highly recommended to use these mechanisms rather than work on raw values.

### Enum

Python style enumerations, examples:

* {py:class}`askiff.gritems.DimensionOrthogonalOrientation`
* {py:class}`askiff.board.ViaType`

::::{grid} 2
:gutter: 2
:padding: 0
:margin:  2 2 0 0

:::{grid-item-card} ✅ Good
:padding: 0
:margin: 0

```python
from askiff.gritems import DimensionOrthogonalOrientation
for dim in footprint.dimensions:
  if dim.orientation == DimensionOrthogonalOrientation.HORIZONTAL:
    ...
```

:::

:::{grid-item-card} ❌ Bad
:padding: 0
:margin: 0

```python
for dim in footprint.dimensions:
  if str(dim.orientation) == '0':
    # Unclear what 0 means
    # May differ in future KiCad revisions
    ...
```

:::

::::

::::{grid} 2
:gutter: 2
:padding: 0
:margin: 2 2 0 0

:::{grid-item-card} ✅ Good
:padding: 0
:margin: 0

```python
from askiff.board import ViaType
pad.type = ViaType.THRU
pad.type = ViaType.BLIND
# Spelling mistakes caught by type checker
# Nicely supported by LSP
```

:::

:::{grid-item-card} ❌ Bad
:padding: 0
:margin: 0

```python
from askiff.board import ViaType
pad.type = '' # Q: What via type is this? A: thru hole
pad.type = 'blind' # May cause incorrect serialization
pad.type = ViaType('blind') # Risk of spelling mistake
```

:::

::::

### Subclasses with hardcoded fields

One of the used patterns is a base abstract class with common fields (e.g. {py:class}`askiff.gritems.Dimension`) and child classes (e.g. {py:class}`askiff.gritems.DimensionOrthogonal`).

Base class is used in class typing but during deserialization it is automatically down casted to a specific subclass, based on a constant field with a keyword indicating the exact subtype.

This approach allows tighter typechecking and prevents setting fields that may be unsupported in this specific subclass.

This also works nicely with fine grained filtration of objects with multi level inheritance, see {py:class}`askiff.gritems.GrItem`

::::{grid} 2
:gutter: 2
:padding: 0
:margin: 2 2 0 0

:::{grid-item-card} ✅ Good
:padding: 0
:margin: 0

```python
from askiff.gritems import DimensionOrthogonal
for dim in footprint.dimensions:
  if isinstance(dim, DimensionOrthogonal):
    # Type checker/LSP know which fields are available
    ...
```

:::

:::{grid-item-card} ❌ Bad
:padding: 0
:margin: 0

```python
for dim in footprint.dimensions:
  if dim.type == 'orthogonal':
    # Spelling mistake risk
    # Type check may later complain about unresolved attributes
    ...
```

:::

::::
::::{grid} 2
:gutter: 2
:padding: 0
:margin: 2 2 0 0

:::{grid-item-card} ✅ Good
:padding: 0
:margin: 0

```python
from askiff.gritems import DimensionOrthogonal, DimensionRadial
dim = DimensionOrthogonal()
# copy just field that are present in new sub type
dim = DimensionRadial(**{k: v for k, v in fp.__dict__.items() if k in DimensionRadial.__dataclass_fields__})
# `dim` is still properly handled by LSP/type checker
```

:::

:::{grid-item-card} ❌ Bad
:padding: 0
:margin: 0

```python
from askiff.gritems import DimensionOrthogonal
dim = DimensionOrthogonal()
dim.type = 'radial'
# New dimension type have different fields, resulting in file that can not be opened by KiCad
```

:::

::::

### Class constants

See {py:class}`askiff.common_pcb.Layer`

## Highlighted classes

Refer to the documentation for more details about the most noteworthy classes:

* {py:class}`askiff.Project` - Unified entry point for the project
* {py:class}`askiff.common_pcb.BaseLayer` - Base class for all layers, describes how to use layer types inheritance
* {py:class}`askiff.common_pcb.LayerSet` - Set of layers that hides few gimmicks of managing layers in PCB/footprint files
* {py:class}`askiff.common.PropertyList` - Accessing symbol/footprint properties
* {py:class}`askiff.gritems.GrItem` - Base class for all graphic items
* {py:class}`askiff.gritems.GrShape` - Base class for graphic items that are simple shapes (rectangle, circle)
* {py:class}`askiff.common.BBox` - Get bounding box/extreme points from a list of shapes

## Symbol types disambiguation

* {py:class}`askiff.symbol.SymbolAspect`
  * Represents part of {py:class}`askiff.symbol.SymbolDefinition` graphics/pins
  * Each instance corresponds to a single symbol unit, alternative style or common part between them
* {py:class}`askiff.symbol.SymbolDefinition`
  * Represents symbol's description in library (graphics and pins)
  * Also used in the schematic file as kind of library cache
* {py:class}`askiff.symbol.SymbolFile`
  * Represents the `kicad_sym` file
  * May contain one or more {py:class}`askiff.symbol.SymbolDefinition`
* {py:class}`askiff.symbol.SymbolSchematic`
  * Instance of symbol on schematic
  * Does not define graphics (refers to {py:class}`askiff.symbol.SymbolDefinition` for that)
  * Stores symbol position, unit, properties
* {py:class}`askiff.symbol.SymbolLibraryTable`
  * Represents `sym-lib-table`
  * Collection of library paths
* {py:class}`askiff.pro.SymbolLibrary`
  * Lazy loaded symbols from a single library
  * Handles both library-per-file & library-per-directory formats via `symbols()` methods
