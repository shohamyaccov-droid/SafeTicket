# Venue Layout System - Implementation Plan

## Overview
This document outlines the flexible solution for handling different venue layouts in the SafeTicket system. The goal is to support multiple venues with different seating configurations while maintaining a scalable architecture.

## Database Schema Design

### Event Model Enhancement
Add a `venue_layout` field to the Event model that stores venue-specific layout configuration as JSON.

**Field Type:** `JSONField` (PostgreSQL) or `TextField` with JSON serialization (SQLite fallback)

**JSON Structure:**
```json
{
  "venue_name": "Menora Mivtachim Arena",
  "venue_type": "stadium",  // "stadium", "theater", "hall", "outdoor"
  "layout_type": "svg",     // "svg", "image", "interactive"
  "svg_id": "menora-mivtachim-default",
  "blocks": [
    {
      "id": "block-1",
      "name": "Block 1",
      "svg_path_id": "block-1-path",
      "display_name": "גוש 1",
      "coordinates": {
        "x": 100,
        "y": 150
      },
      "capacity": 500,
      "sections": ["1", "2", "3"]
    },
    {
      "id": "block-11",
      "name": "Block 11",
      "svg_path_id": "block-11-path",
      "display_name": "גוש 11",
      "coordinates": {
        "x": 300,
        "y": 200
      },
      "capacity": 300,
      "sections": ["11"]
    }
    // ... more blocks
  ],
  "metadata": {
    "created_at": "2025-01-01T00:00:00Z",
    "updated_at": "2025-01-01T00:00:00Z",
    "version": "1.0"
  }
}
```

### Key Design Decisions

1. **Flexible Block Mapping:**
   - Each block has a unique `id` (e.g., "block-11")
   - The `svg_path_id` maps to the actual SVG element ID in the rendered map
   - The `name` field stores the human-readable name (e.g., "Block 11")
   - The `display_name` field stores the Hebrew name (e.g., "גוש 11")

2. **Seller Input Mapping:**
   - When a seller enters "Block 11" or "גוש 11" in the `section` field, the system will:
     - Normalize the input (remove spaces, convert to lowercase)
     - Match against block `name`, `display_name`, or `id`
     - Store the normalized block ID in the ticket's `section` field

3. **Default Layout for Menora Mivtachim:**
   - Create a default layout JSON with common blocks (1-20)
   - This will be used as a template for new events at this venue
   - Can be customized per event if needed

## Implementation Steps

### Phase 1: Backend Schema
1. Add `venue_layout` field to Event model
2. Create migration
3. Add default Menora Mivtachim layout
4. Update EventSerializer to include `venue_layout`

### Phase 2: Frontend SVG Integration
1. Create reusable SVG seat map component
2. Parse venue_layout JSON to render blocks
3. Make blocks clickable
4. Add visual feedback (hover, selected, available)

### Phase 3: Interactive Filtering
1. Connect block clicks to filter state
2. Update ticket list when block is selected
3. Highlight blocks with available tickets
4. Show ticket count per block

### Phase 4: Seller Integration
1. Update seller form to show venue-specific block selector
2. Map seller input to SVG block IDs
3. Validate block selection against venue layout

## Example: Menora Mivtachim Default Layout

```json
{
  "venue_name": "Menora Mivtachim Arena",
  "venue_type": "stadium",
  "layout_type": "svg",
  "svg_id": "menora-mivtachim-default",
  "blocks": [
    {"id": "block-1", "name": "Block 1", "svg_path_id": "block-1", "display_name": "גוש 1"},
    {"id": "block-2", "name": "Block 2", "svg_path_id": "block-2", "display_name": "גוש 2"},
    {"id": "block-3", "name": "Block 3", "svg_path_id": "block-3", "display_name": "גוש 3"},
    {"id": "block-4", "name": "Block 4", "svg_path_id": "block-4", "display_name": "גוש 4"},
    {"id": "block-5", "name": "Block 5", "svg_path_id": "block-5", "display_name": "גוש 5"},
    {"id": "block-6", "name": "Block 6", "svg_path_id": "block-6", "display_name": "גוש 6"},
    {"id": "block-7", "name": "Block 7", "svg_path_id": "block-7", "display_name": "גוש 7"},
    {"id": "block-8", "name": "Block 8", "svg_path_id": "block-8", "display_name": "גוש 8"},
    {"id": "block-9", "name": "Block 9", "svg_path_id": "block-9", "display_name": "גוש 9"},
    {"id": "block-10", "name": "Block 10", "svg_path_id": "block-10", "display_name": "גוש 10"},
    {"id": "block-11", "name": "Block 11", "svg_path_id": "block-11", "display_name": "גוש 11"},
    {"id": "block-12", "name": "Block 12", "svg_path_id": "block-12", "display_name": "גוש 12"},
    {"id": "block-13", "name": "Block 13", "svg_path_id": "block-13", "display_name": "גוש 13"},
    {"id": "block-14", "name": "Block 14", "svg_path_id": "block-14", "display_name": "גוש 14"},
    {"id": "block-15", "name": "Block 15", "svg_path_id": "block-15", "display_name": "גוש 15"},
    {"id": "block-16", "name": "Block 16", "svg_path_id": "block-16", "display_name": "גוש 16"},
    {"id": "block-17", "name": "Block 17", "svg_path_id": "block-17", "display_name": "גוש 17"},
    {"id": "block-18", "name": "Block 18", "svg_path_id": "block-18", "display_name": "גוש 18"},
    {"id": "block-19", "name": "Block 19", "svg_path_id": "block-19", "display_name": "גוש 19"},
    {"id": "block-20", "name": "Block 20", "svg_path_id": "block-20", "display_name": "גוש 20"}
  ],
  "metadata": {
    "created_at": "2025-01-01T00:00:00Z",
    "version": "1.0"
  }
}
```

## Block ID Normalization Logic

When a seller enters a section/block:
- Input: "Block 11" → Normalized: "block-11"
- Input: "גוש 11" → Normalized: "block-11"
- Input: "11" → Normalized: "block-11"
- Input: "block-11" → Normalized: "block-11"

This ensures consistent mapping between seller input and SVG block IDs.

## Benefits of This Approach

1. **Flexibility:** Each venue can have a completely different layout
2. **Scalability:** Easy to add new venues without code changes
3. **Maintainability:** Layout data stored in database, not hardcoded
4. **Extensibility:** Can add more metadata (pricing zones, accessibility info, etc.)
5. **Backward Compatibility:** Events without venue_layout will gracefully degrade

## Next Steps

1. Review and approve this schema design
2. Implement backend changes (Event model + migration)
3. Create default Menora Mivtachim layout
4. Build SVG component
5. Integrate with EventDetailsPage
6. Add filtering functionality



