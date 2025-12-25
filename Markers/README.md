# Circle with Markers Generator

Two Python scripts for generating SVG vector images of black circles with randomly placed markers. Perfect for creating calibration targets, scanning patterns, or visual markers for computer vision applications.

## Scripts

### `generate_circle.py`
Generates complex markers with multiple concentric rings (black and white alternating rings). These complex markers are used in FlexScan3D software.

### `generate_circle_simple.py`
Generates simple markers with a single black ring and white center.

## Requirements

- Python 3.x
- Standard library only (no external dependencies)

## Usage

### Basic Usage

**Complex markers:**
```bash
python3 generate_circle.py <circle_diameter_mm> <marker_diameter_mm> <num_markers>
```

**Simple markers:**
```bash
python3 generate_circle_simple.py <circle_diameter_mm> <marker_diameter_mm> <num_markers>
```

### Arguments

- `circle_diameter_mm` - Diameter of the black background circle in millimeters (required)
- `marker_diameter_mm` - Diameter of each marker in millimeters (required)
- `num_markers` - Number of markers to place on the circle (required)

### Options

- `--output <filename>` - Output SVG filename (default: auto-generated based on parameters)
- `--margin <mm>` - Margin around the circle in mm (default: 5.0)
- `--mean-spacing <mm>` - Mean spacing between markers in mm (default: 0.0, meaning just touching)
- `--std-spacing <mm>` - Standard deviation of spacing between markers in mm (default: 0.0, meaning fixed spacing)

### Examples

Generate a 100mm circle with 30 complex markers of 10mm diameter:
```bash
python3 generate_circle.py 100 10 30
```

Generate a 50mm circle with 20 simple markers of 5mm diameter, with custom output filename:
```bash
python3 generate_circle_simple.py 50 5 20 --output my_calibration_target.svg
```

Generate markers with random spacing (normal distribution):
```bash
python3 generate_circle.py 100 10 30 --mean-spacing 2.0 --std-spacing 0.5
```

## Marker Design

### Complex Markers (`generate_circle.py`)

These complex markers are used in FlexScan3D software.

Each marker consists of:
1. **White border circle** - Separates marker from black background (configurable width)
2. **First black ring** - Outermost black ring (configurable thickness)
3. **First white ring** - Thin white ring (configurable thickness)
4. **Second black ring** - Thick black ring (configurable thickness)
5. **Center white circle** - Remaining area filled with white

### Simple Markers (`generate_circle_simple.py`)

Each marker consists of:
1. **White border circle** - Separates marker from black background (configurable width)
2. **Black ring** - Single black ring (configurable thickness)
3. **White center circle** - Remaining area filled with white

## Configuration Constants

Both scripts can be customized by editing constants at the top of the file.

### `generate_circle.py`

```python
# White border width as percentage of marker radius
WHITE_BORDER_PERCENT = 50.0  # White border thickness (% of marker radius)

# Marker ring proportions (as percentages of radius)
FIRST_BLACK_RING_PERCENT = 10.0   # Outermost black ring thickness (%)
FIRST_WHITE_RING_PERCENT = 15.0   # Thin white ring thickness (%)
SECOND_BLACK_RING_PERCENT = 30.0  # Thick black ring thickness (%)
# Center white circle is the remaining percentage
```

**Note:** The sum of `FIRST_BLACK_RING_PERCENT`, `FIRST_WHITE_RING_PERCENT`, and `SECOND_BLACK_RING_PERCENT` must be ≤ 100%.

### `generate_circle_simple.py`

```python
# White border width as percentage of marker radius
WHITE_BORDER_PERCENT = 20.0  # White border thickness (% of marker radius)

# Black ring width as percentage of marker radius
BLACK_RING_PERCENT = 30.0  # Black ring thickness (% of marker radius)
# Center white circle is the remaining percentage
```

**Note:** `BLACK_RING_PERCENT` must be ≤ 100%.

## Features

- **Vector output** - Generates SVG files that scale perfectly at any size
- **Collision detection** - Prevents markers from overlapping
- **Uniform distribution** - Markers are distributed evenly across the circle area (not clustered near center)
- **Random spacing** - Optional normal distribution for spacing between markers
- **Configurable design** - Adjust marker proportions via constants

## Output

Both scripts generate SVG (Scalable Vector Graphics) files that can be:
- Opened in any web browser
- Imported into design software (Inkscape, Illustrator, etc.)
- Printed at any scale
- Used in 3D printing slicers
- Converted to other formats (PDF, PNG, etc.)

## Algorithm

### Marker Placement

1. Markers are placed randomly within the circle bounds
2. Distance from center uses square root distribution to ensure uniform area coverage
3. Collision detection ensures markers don't overlap (accounts for white borders)
4. Random spacing can be applied with normal distribution

### Collision Detection

- Each marker has an effective radius that includes its white border
- Minimum distance between marker centers = `2 × effective_radius + spacing`
- Placement attempts up to 1000 times before giving up (warns if placement fails)

## Tips

- **Large numbers of markers**: If you can't place all requested markers, try:
  - Reducing marker diameter
  - Increasing circle diameter
  - Reducing `WHITE_BORDER_PERCENT`
  - Using negative `--mean-spacing` to allow slight overlap (not recommended)

- **Printing**: SVG files can be printed directly or converted to PDF/PNG first

- **3D Printing**: Import SVG into your slicer or convert to STL using tools like OpenSCAD

## License

This code is provided as-is for use in your projects.

