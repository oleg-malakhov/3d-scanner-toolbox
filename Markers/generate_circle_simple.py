#!/usr/bin/env python3
"""
Generate an SVG vector image of a black circle with randomly placed simple markers.
Each marker is just a black circle outline with white fill inside.

Usage:
    python generate_circle_simple.py <circle_diameter_mm> <marker_diameter_mm> <num_markers>

Example:
    python generate_circle_simple.py 100 10 5
"""

import argparse
import random
import math
from pathlib import Path
import sys
import xml.etree.ElementTree as ET

# White border width as percentage of marker radius
WHITE_BORDER_PERCENT = 20.0  # White border thickness (% of marker radius)

# Black ring width as percentage of marker radius
BLACK_RING_PERCENT = 30.0  # Black ring thickness (% of marker radius)
# Center white circle is the remaining percentage

# Validate that constants are <= 100%
if BLACK_RING_PERCENT > 100.0:
    raise ValueError(
        f"Black ring percentage ({BLACK_RING_PERCENT}%) exceeds 100%. "
        f"Please adjust BLACK_RING_PERCENT constant."
    )
if WHITE_BORDER_PERCENT < 0.0:
    raise ValueError(
        f"White border percentage ({WHITE_BORDER_PERCENT}%) must be non-negative. "
        f"Please adjust WHITE_BORDER_PERCENT constant."
    )


def create_simple_marker_svg(marker_diameter_mm, marker_id, center_x, center_y):
    """
    Create SVG elements for a simple marker:
    1. White border circle (outermost, to separate from black background)
    2. Black ring (with constant width percentage)
    3. White center circle (the rest)
    
    Args:
        marker_diameter_mm: Diameter of the marker (without white border)
        marker_id: Unique ID for the marker
        center_x: X coordinate of marker center
        center_y: Y coordinate of marker center
    
    Returns:
        List of SVG elements.
    """
    elements = []
    radius = marker_diameter_mm / 2
    
    # White border thickness as percentage of marker radius
    white_border_thickness = radius * (WHITE_BORDER_PERCENT / 100.0)
    white_border_radius = radius + white_border_thickness
    
    # Draw white border circle (outermost)
    white_border = ET.Element('circle')
    white_border.set('cx', str(center_x))
    white_border.set('cy', str(center_y))
    white_border.set('r', str(white_border_radius))
    white_border.set('fill', 'white')
    elements.append(white_border)
    
    # Calculate black ring dimensions
    # Black ring outer radius = marker radius (100%)
    black_ring_outer = radius
    # Black ring inner radius = marker radius - (BLACK_RING_PERCENT% of radius)
    black_ring_inner = radius * (1.0 - BLACK_RING_PERCENT / 100.0)
    
    # Center white circle radius = black ring inner radius
    center_white_radius = black_ring_inner
    
    # Helper function to create a ring using two circles
    def create_ring(cx, cy, outer_r, inner_r, ring_color, background_color):
        """Create a ring by drawing outer circle with ring color, then inner circle with background color."""
        if outer_r <= inner_r:
            return None
        
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
    
    # Draw black ring (on white background from white border)
    if black_ring_outer > black_ring_inner:
        ring = create_ring(center_x, center_y, black_ring_outer, black_ring_inner, 'black', 'white')
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
        marker_radius_mm: Radius of the marker
        marker_id: ID of the marker (for error messages)
        mean_spacing_mm: Mean spacing between markers (default: 0, meaning just touching)
        std_spacing_mm: Standard deviation of spacing (default: 0, meaning fixed spacing)
    
    Returns:
        (x, y) position of the marker, or None if placement failed
    """
    max_attempts = 1000
    
    for attempt in range(max_attempts):
        # Random angle
        angle = random.uniform(0, 2 * math.pi)
        
        # Random distance from center (ensuring marker stays within circle)
        # Account for white border (as percentage of marker radius)
        white_border_thickness = marker_radius_mm * (WHITE_BORDER_PERCENT / 100.0)
        effective_marker_radius = marker_radius_mm + white_border_thickness
        
        # Maximum distance from center where marker still fits
        max_distance = circle_radius_mm - effective_marker_radius
        
        if max_distance <= 0:
            print(f"Error: Marker {marker_id} is too large to fit in circle", file=sys.stderr)
            return None
        
        # Random distance with uniform distribution across area
        # Since area increases with r^2, we use sqrt to get uniform area distribution
        # This ensures markers spread evenly across the circle, not clustered near center
        distance = math.sqrt(random.uniform(0, 1)) * max_distance
        
        # Calculate position
        x = circle_center_mm[0] + distance * math.cos(angle)
        y = circle_center_mm[1] + distance * math.sin(angle)
        
        # Check collision with existing markers
        # Account for white border in collision detection
        random_spacing = max(0.0, random.gauss(mean_spacing_mm, std_spacing_mm))
        min_distance_between_centers = 2 * effective_marker_radius + random_spacing
        
        collision = False
        for existing_x, existing_y in marker_positions:
            dx = x - existing_x
            dy = y - existing_y
            distance_between = math.sqrt(dx * dx + dy * dy)
            
            if distance_between < min_distance_between_centers:
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
        description='Generate an SVG vector image of a black circle with randomly placed simple markers.',
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
                        help='Output filename (default: circle_simple_<diameter>mm_<num>markers.svg)')
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
            marker_elements = create_simple_marker_svg(args.marker_diameter, i + 1, 
                                                       position[0], position[1])
            for element in marker_elements:
                svg.append(element)
            placed_count += 1
    
    if placed_count < args.num_markers:
        print(f"Warning: Only placed {placed_count} out of {args.num_markers} markers", 
              file=sys.stderr)
    
    # Generate output filename if not provided
    if args.output is None:
        args.output = f"circle_simple_{int(args.circle_diameter)}mm_{args.num_markers}markers.svg"
    
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

