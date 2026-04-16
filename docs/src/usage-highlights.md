# Usage Highlights

## Typing oriented

Library is built around python static typing system (type annotations) and dataclasses.
To ensure correct serialization it is necessary to ensure type correctness when assigning to objects/fields defined in this library.
The most robust way and one strongly recommended is to use type checkers (e.g. mypy, ty, ...).
Assigning incorrect type object is likely to lead to runtime exceptions or corrupted files.

## Mirrors KiCad file structure

Most of classes and their fields directly mirror structure/map to objects in KiCad files.

`Final` typed fields or `_askiff_key` field match keyword used in KiCad files and should never be changed.
If it seems to necessary to change them, other, related class should probably be used.
From the point of python interface they are irrelevant.

## Enum based values

KiCad files use multiple keywords and constant values to indicate object subtype or some setting value.

To reduce risk of spelling error and to make usage more clear, `askiff` abstracts this using 3 methods.
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

### Subclasses with hardcoded field

One of used patterns is base abstract class with common fields (e.g. {py:class}`askiff.gritems.Dimension`) and child classes (e.g. {py:class}`askiff.gritems.DimensionOrthogonal`).

Base class is used in class typing but during deserialization it is automatically down casted to specific subclass, based on constant field with keyword indicating exact subtype.

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

## Highlighted Classes

Few classes worth noticing as they extend slightly beyond simple resembling of KiCad structures, see their documentation

* {py:class}`askiff.Project` - Unified entry point for project
* {py:class}`askiff.common_pcb.BaseLayer` - Base class for all layers, describes how to use layer types inheritance
* {py:class}`askiff.common_pcb.LayerSet` - Set of layers that hides few gimmicks of managing layers in PCB/footprint files
* {py:class}`askiff.common.PropertyList` - Accessing symbol/footprint properties
* {py:class}`askiff.gritems.GrItem` - Base class for all graphic items
* {py:class}`askiff.gritems.GrShape` - Base class for graphic items that are simple shapes (rectangle, circle)
* {py:class}`askiff.common.BBox` - Get bounding box/extreme points from list of shapes

## Symbol types disambiguation

* {py:class}`askiff.symbol.SymbolAspect`
  * Represents part of {py:class}`askiff.symbol.SymbolDefinition` graphics/pins
  * Each instance corresponds to single symbol unit, alternative style or common part between them
* {py:class}`askiff.symbol.SymbolDefinition`
  * Represents symbol's description in library (graphics and pins)
  * Also used in schematic file as kind of library cache
* {py:class}`askiff.symbol.SymbolFile`
  * Represents `kicad_sym` file
  * May contain one or more {py:class}`askiff.symbol.SymbolDefinition`
* {py:class}`askiff.symbol.SymbolSchematic`
  * Instance of symbol on schematic
  * Does not define graphics (refers to {py:class}`askiff.symbol.SymbolDefinition` for that)
  * Stores symbol position, unit, properties
* {py:class}`askiff.symbol.SymbolLibraryTable`
  * Represents `sym-lib-table`
  * Collection of library paths
* {py:class}`askiff.pro.SymbolLibrary`
  * Lazy loaded symbols from single library
  * Handles both library-per-file & library-per-directory formats via `symbols()` methods
