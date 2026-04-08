# Quick start

## Installation

```bash
pip install 'git+https://github.com/antmicro/askiff.git'
```

## Examples

## Load project from path

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

## Create new PCB

It is also possible to operate directly on specific KiCad file only.

```python
from askiff.board import Board

# Create a new board
board = Board()

# Save created board to file
board.to_file("path/to/pcb.kicad_pcb")
```

## Add footprint to PCB

Load an existing PCB, add a footprint, and save the updated PCB.

```python
from askiff import Project
from askiff.footprint import FootprintFile

# Load a KiCad project
project = Project("path/to/project").load()

# Load footprint (from project library)
footprint = project.fp["ResistorLib"]["Resistor0402"]

# OR Load footprint (from file)
footprint = FootprintFile.from_file("path/to/footprint.kicad_mod")

# Add footprint to board
project.pcb[0].add_footprint(footprint, reference="R1", position=Position(15, 20))

# Save the project
project.save()
```

## Get Bounding box of all shapes on Silkscreen layers

Askiff allows also to operate directly on specific KiCad file only (without Project).

```python
from askiff.board import Board
from askiff.pcb_common import LayerSilkS
from askiff.common import BBox

# Load Board
Board.from_file("path/to/pcb.kicad_pcb")

# Get all Silkscreen shapes
silkscreen_items = [
    item for item in board.graphic_items
    if isinstance(item, GrShapePCB) # Filter shapes using base class for all shapes on PCB
        # To get just eg. rectangles and circles use `isinstance(item, (GrCirclePCB, GrRectPCB))`
        and isinstance(item.layer, LayerSilkS) # filter layers to that inheriting from LayerSilkS (that is Layer.SILKS_F or Layer.SILKS_B)
        # Layer type are also inheritance based, eg. parent class `LayerTech` can be used to get all technical layers such as SilkS, Fab, Mask, ..
]

# Get bounding box of shapes
bbox = BBox.from_shapes(silkscreen_items)

print(f"Bounding box: ({bbox.start.x},{bbox.start.y}) : ({bbox.end.x},{bbox.end.y})")
```

## Simple DFN footprint generator

Simple DFN footprint generator with configurable pins and pitch.

```python
from askiff.common import LibId, Position, Size
from askiff.common_pcb import Layer, LayerSet
from askiff.footprint import FootprintFile
from askiff.fp_pad import PadShapeRoundrect, PadSMD
from askiff.gritems import GrRectFp

def generate_dfn_footprint(name: str, pins: int, pitch: float, row_spacing: float) -> FootprintFile:
    # Initialize empty footprint
    footprint = FootprintFile(lib_id=LibId(name=name))

    pad_shape = PadShapeRoundrect(size=Size(0.4, 0.2))
    pad_layers = LayerSet(Layer.CU_F, Layer.MASK_F, Layer.PASTE_F)

    # Add pads
    for i in range(pins):
        y = (i % (pins / 2)) * pitch
        x = 0 if i < pins / 2 else row_spacing
        pad = PadSMD(number=str(i+1), shape=pad_shape, position=Position(x, y), layers=pad_layers)
        footprint.pads.append(pad)

    # Add courtyard
    courtyard_rect = GrRectFp(
        start=Position(x=0, y=-pitch * 0.5),
        end=Position(x=row_spacing, y=(pins / 2 - 0.5) * pitch),
        layer=Layer.COURTYARD_F,
    )
    footprint.graphic_items.append(courtyard_rect)

    return footprint

# Create a DFN footprint
dfn = generate_dfn_footprint("DFN16", 16, 0.65, 1.25)
dfn.to_file("path/to/dfn16.kicad_mod")
```
