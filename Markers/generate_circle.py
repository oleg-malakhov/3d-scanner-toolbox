#!/usr/bin/env python3
"""
Generate an SVG vector image of a black circle with randomly placed markers.

Usage:
    python generate_circle.py <circle_diameter_mm> <marker_diameter_mm> <num_markers>

Example:
    python generate_circle.py 100 10 5
"""

import argparse
import random
import math
from pathlib import Path
import sys
import xml.etree.ElementTree as ET

# White border width as percentage of marker radius
WHITE_BORDER_PERCENT = 50.0  # White border thickness (% of marker radius)

# Marker ring proportions (as percentages of radius)
# These define the thickness of each ring from outer to inner
FIRST_BLACK_RING_PERCENT = 10.0   # Outermost black ring thickness (%)
FIRST_WHITE_RING_PERCENT = 15.0   # Thin white ring thickness (%)
SECOND_BLACK_RING_PERCENT = 30.0 # Thick black ring thickness (%)
# Center white circle is the remaining percentage

# Validate that constants are valid
if WHITE_BORDER_PERCENT < 0.0:
    raise ValueError(
        f"White border percentage ({WHITE_BORDER_PERCENT}%) must be non-negative. "
        f"Please adjust WHITE_BORDER_PERCENT constant."
    )

# Validate that sum of constants is <= 100%
_RING_SUM = FIRST_BLACK_RING_PERCENT + FIRST_WHITE_RING_PERCENT + SECOND_BLACK_RING_PERCENT
if _RING_SUM > 100.0:
    raise ValueError(
        f"Sum of ring percentages ({_RING_SUM}%) exceeds 100%. "
        f"Please adjust the constants: FIRST_BLACK_RING_PERCENT, "
        f"FIRST_WHITE_RING_PERCENT, SECOND_BLACK_RING_PERCENT"
    )

CENTER_CIRCLE_PERCENT = 100.0 - _RING_SUM


def create_marker_svg(marker_diameter_mm, marker_id, center_x, center_y, svg_defs=None):
    """
    Create SVG elements for a marker based on the design constants.
    
    Args:
        marker_diameter_mm: Diameter of the marker
        marker_id: Unique ID for the marker
        center_x: X coordinate of marker center
        center_y: Y coordinate of marker center
        svg_defs: SVG defs element to add mask definitions to (optional)
    
    Returns:
        List of SVG elements.
    """
    radius = marker_diameter_mm / 2
    elements = []
    
    # Draw thick white circle around marker (separates marker from black background)
    # White border thickness as percentage of marker radius
    white_border_thickness = radius * (WHITE_BORDER_PERCENT / 100.0)
    white_border_radius = radius + white_border_thickness
    white_border = ET.Element('circle')
    white_border.set('cx', str(center_x))
    white_border.set('cy', str(center_y))
    white_border.set('r', str(white_border_radius))
    white_border.set('fill', 'white')
    elements.append(white_border)
    
    # Calculate ring positions from outer to inner using constants
    # Start from 100% (outer edge) and work inward
    current_radius = 1.0  # 100% of radius
    
    # First black ring
    outer_black_outer = radius * current_radius
    current_radius -= FIRST_BLACK_RING_PERCENT / 100.0
    outer_black_inner = radius * current_radius
    
    # First white ring
    white_ring_outer = radius * current_radius
    current_radius -= FIRST_WHITE_RING_PERCENT / 100.0
    white_ring_inner = radius * current_radius
    
    # Second black ring
    inner_black_outer = radius * current_radius
    current_radius -= SECOND_BLACK_RING_PERCENT / 100.0
    inner_black_inner = radius * current_radius
    
    # Center white circle (remaining)
    center_white_radius = radius * current_radius
    
    # Helper function to create a ring using two circles
    def create_ring(cx, cy, outer_r, inner_r, ring_color, background_color):
        """Create a ring by drawing outer circle with ring color, then inner circle with background color."""
        if outer_r <= inner_r:
            return None
        
        # Create a group to hold both circles
        g = ET.Element('g')
        
        # Outer circle with ring color
        outer_circle = ET.Element('circle')
        outer_circle.set('cx', str(cx))
        outer_circle.set('cy', str(cy))
        outer_circle.set('r', str(outer_r))
        outer_circle.set('fill', ring_color)
        g.append(outer_circle)
        
        # Inner circle with background color (creates the hole)
        inner_circle = ET.Element('circle')
        inner_circle.set('cx', str(cx))
        inner_circle.set('cy', str(cy))
        inner_circle.set('r', str(inner_r))
        inner_circle.set('fill', background_color)
        g.append(inner_circle)
        
        return g
    
    # Draw first black ring (on white background from white border)
    if outer_black_outer > outer_black_inner:
        ring = create_ring(center_x, center_y, outer_black_outer, outer_black_inner, 'black', 'white')
        if ring is not None:
            elements.append(ring)
    
    # Draw thin white ring (on black background from first black ring)
    if white_ring_outer > white_ring_inner:
        ring = create_ring(center_x, center_y, white_ring_outer, white_ring_inner, 'white', 'black')
        if ring is not None:
            elements.append(ring)
    
    # Draw second black ring (on white background from white ring)
    if inner_black_outer > inner_black_inner:
        ring = create_ring(center_x, center_y, inner_black_outer, inner_black_inner, 'black', 'white')
        if ring is not None:
            elements.append(ring)
    
    # Draw center white circle
    if center_white_radius > 0:
        circle = ET.Element('circle')
        circle.set('cx', str(center_x))
        circle.set('cy', str(center_y))
        circle.set('r', str(center_white_radius))
        circle.set('fill', 'white')
        elements.append(circle)
    
    return elements


def place_marker_randomly(marker_positions, circle_center_mm, circle_radius_mm, marker_radius_mm, marker_id, 
                         mean_spacing_mm=0.0, std_spacing_mm=0.0):
    """
    Place a marker at a random position within the circle.
    Ensures the marker stays within the circle bounds and doesn't collide with existing markers.
    Uses random spacing with normal distribution between markers.
    
    Args:
        marker_positions: List of (x, y) positions of already placed markers
        circle_center_mm: (x, y) center of the circle
        circle_radius_mm: Radius of the circle
        marker_radius_mm: Radius of the marker (without white border)
        marker_id: ID of the marker (for error messages)
        mean_spacing_mm: Mean spacing between markers (default: 0, meaning just touching)
        std_spacing_mm: Standard deviation of spacing (default: 0, meaning fixed spacing)
    
    Returns:
        (x, y) position or None if placement failed.
    """
    # Account for white border (as percentage of marker radius)
    white_border_thickness = marker_radius_mm * (WHITE_BORDER_PERCENT / 100.0)
    effective_marker_radius = marker_radius_mm + white_border_thickness
    
    # Generate random spacing for this marker placement (normal distribution)
    # Ensure spacing is non-negative by truncating at 0
    spacing = max(0.0, random.gauss(mean_spacing_mm, std_spacing_mm))
    
    # Minimum distance between marker centers to avoid collision
    # Need 2 * effective_radius + random spacing
    min_distance_between_centers = 2 * effective_marker_radius + spacing
    
    max_attempts = 500  # Increased attempts for better placement
    for attempt in range(max_attempts):
        # Generate random angle and distance from center
        angle = random.uniform(0, 2 * math.pi)
        # Distance from center, ensuring marker (with border) stays within circle
        max_distance = circle_radius_mm - effective_marker_radius
        if max_distance <= 0:
            # If marker is larger than circle, place at center
            x = circle_center_mm[0]
            y = circle_center_mm[1]
        else:
            # Random distance with uniform distribution across area
            # Since area increases with r^2, we use sqrt to get uniform area distribution
            # This ensures markers spread evenly across the circle, not clustered near center
            distance = math.sqrt(random.uniform(0, 1)) * max_distance
            x = circle_center_mm[0] + distance * math.cos(angle)
            y = circle_center_mm[1] + distance * math.sin(angle)
        
        # Check if this position collides with existing markers
        collision = False
        for existing_x, existing_y in marker_positions:
            dist = math.sqrt((x - existing_x)**2 + (y - existing_y)**2)
            if dist < min_distance_between_centers:
                collision = True
                break
        
        if not collision:
            marker_positions.append((x, y))
            return (x, y)
    
    # If we couldn't place it after max attempts, return None
    print(f"Warning: Could not place marker {marker_id} after {max_attempts} attempts", file=sys.stderr)
    return None


def main():
    parser = argparse.ArgumentParser(
        description='Generate an SVG vector image of a black circle with randomly placed markers.',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__
    )
    parser.add_argument('circle_diameter', type=float,
                        help='Diameter of the black circle in mm')
    parser.add_argument('marker_diameter', type=float,
                        help='Diameter of each marker in mm')
    parser.add_argument('num_markers', type=int,
                        help='Number of markers to place on the circle')
    parser.add_argument('--output', type=str, default=None,
                        help='Output filename (default: circle_<diameter>mm_<num>markers.svg)')
    parser.add_argument('--margin', type=float, default=5.0,
                        help='Margin around circle in mm (default: 5.0)')
    parser.add_argument('--mean-spacing', type=float, default=0.0,
                        help='Mean spacing between markers in mm (default: 0.0, meaning just touching)')
    parser.add_argument('--std-spacing', type=float, default=0.0,
                        help='Standard deviation of spacing between markers in mm (default: 0.0, meaning fixed spacing)')
    
    args = parser.parse_args()
    
    # Validate arguments
    if args.circle_diameter <= 0:
        print("Error: Circle diameter must be positive", file=sys.stderr)
        sys.exit(1)
    if args.marker_diameter <= 0:
        print("Error: Marker diameter must be positive", file=sys.stderr)
        sys.exit(1)
    if args.num_markers < 0:
        print("Error: Number of markers must be non-negative", file=sys.stderr)
        sys.exit(1)
    
    # Calculate dimensions in mm (SVG uses mm directly)
    circle_radius_mm = args.circle_diameter / 2
    marker_radius_mm = args.marker_diameter / 2
    margin_mm = args.margin
    
    # Calculate SVG viewBox dimensions
    svg_width = args.circle_diameter + 2 * margin_mm
    svg_height = args.circle_diameter + 2 * margin_mm
    circle_center_mm = (svg_width / 2, svg_height / 2)
    
    # Create SVG root element
    svg = ET.Element('svg')
    svg.set('xmlns', 'http://www.w3.org/2000/svg')
    svg.set('width', f'{svg_width}mm')
    svg.set('height', f'{svg_height}mm')
    svg.set('viewBox', f'0 0 {svg_width} {svg_height}')
    
    # White background rectangle
    background = ET.Element('rect')
    background.set('width', str(svg_width))
    background.set('height', str(svg_height))
    background.set('fill', 'white')
    svg.append(background)
    
    # Draw black circle
    circle = ET.Element('circle')
    circle.set('cx', str(circle_center_mm[0]))
    circle.set('cy', str(circle_center_mm[1]))
    circle.set('r', str(circle_radius_mm))
    circle.set('fill', 'black')
    svg.append(circle)
    
    # Place markers randomly
    marker_positions = []
    placed_count = 0
    for i in range(args.num_markers):
        position = place_marker_randomly(marker_positions, circle_center_mm, 
                                         circle_radius_mm, marker_radius_mm, i + 1,
                                         args.mean_spacing, args.std_spacing)
        if position:
            # Create marker SVG elements
            marker_elements = create_marker_svg(args.marker_diameter, i + 1, 
                                               position[0], position[1])
            for element in marker_elements:
                svg.append(element)
            placed_count += 1
    
    if placed_count < args.num_markers:
        print(f"Warning: Only placed {placed_count} out of {args.num_markers} markers", 
              file=sys.stderr)
    
    # Generate output filename if not provided
    if args.output is None:
        args.output = f"circle_{int(args.circle_diameter)}mm_{args.num_markers}markers.svg"
    
    # Save SVG file
    script_dir = Path(__file__).parent
    output_path = script_dir / args.output
    
    # Format and write SVG
    ET.indent(svg, space="  ")
    tree = ET.ElementTree(svg)
    tree.write(output_path, encoding='utf-8', xml_declaration=True)
    
    print(f"Generated SVG: {output_path}")
    print(f"  Circle diameter: {args.circle_diameter} mm")
    print(f"  Marker diameter: {args.marker_diameter} mm")
    print(f"  Markers placed: {placed_count}/{args.num_markers}")
    print(f"  SVG size: {svg_width}mm x {svg_height}mm")


if __name__ == '__main__':
    main()
