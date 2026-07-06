---
name: Nexus Codex
colors:
  surface: '#FFFFFF'
  surface-dim: '#d8dadc'
  surface-bright: '#f7f9fb'
  surface-container-lowest: '#ffffff'
  surface-container-low: '#f2f4f6'
  surface-container: '#eceef0'
  surface-container-high: '#e6e8ea'
  surface-container-highest: '#e0e3e5'
  on-surface: '#191c1e'
  on-surface-variant: '#464555'
  inverse-surface: '#2d3133'
  inverse-on-surface: '#eff1f3'
  outline: '#777587'
  outline-variant: '#c7c4d8'
  surface-tint: '#4d44e3'
  primary: '#3525cd'
  on-primary: '#ffffff'
  primary-container: '#4f46e5'
  on-primary-container: '#dad7ff'
  inverse-primary: '#c3c0ff'
  secondary: '#505f76'
  on-secondary: '#ffffff'
  secondary-container: '#d0e1fb'
  on-secondary-container: '#54647a'
  tertiary: '#7e3000'
  on-tertiary: '#ffffff'
  tertiary-container: '#a44100'
  on-tertiary-container: '#ffd2be'
  error: '#ba1a1a'
  on-error: '#ffffff'
  error-container: '#ffdad6'
  on-error-container: '#93000a'
  primary-fixed: '#e2dfff'
  primary-fixed-dim: '#c3c0ff'
  on-primary-fixed: '#0f0069'
  on-primary-fixed-variant: '#3323cc'
  secondary-fixed: '#d3e4fe'
  secondary-fixed-dim: '#b7c8e1'
  on-secondary-fixed: '#0b1c30'
  on-secondary-fixed-variant: '#38485d'
  tertiary-fixed: '#ffdbcc'
  tertiary-fixed-dim: '#ffb695'
  on-tertiary-fixed: '#351000'
  on-tertiary-fixed-variant: '#7b2f00'
  background: '#f7f9fb'
  on-background: '#191c1e'
  surface-variant: '#e0e3e5'
  success: '#10B981'
  warning: '#F59E0B'
  border: '#E2E8F0'
  text-primary: '#0F172A'
  text-secondary: '#475569'
typography:
  headline-lg:
    fontFamily: Inter
    fontSize: 30px
    fontWeight: '700'
    lineHeight: 38px
    letterSpacing: -0.02em
  headline-md:
    fontFamily: Inter
    fontSize: 24px
    fontWeight: '600'
    lineHeight: 32px
    letterSpacing: -0.01em
  headline-sm:
    fontFamily: Inter
    fontSize: 18px
    fontWeight: '600'
    lineHeight: 26px
  body-lg:
    fontFamily: Inter
    fontSize: 16px
    fontWeight: '400'
    lineHeight: 24px
  body-md:
    fontFamily: Inter
    fontSize: 14px
    fontWeight: '400'
    lineHeight: 20px
  body-sm:
    fontFamily: Inter
    fontSize: 13px
    fontWeight: '400'
    lineHeight: 18px
  label-md:
    fontFamily: JetBrains Mono
    fontSize: 12px
    fontWeight: '500'
    lineHeight: 16px
    letterSpacing: 0.02em
  label-sm:
    fontFamily: JetBrains Mono
    fontSize: 11px
    fontWeight: '500'
    lineHeight: 14px
    letterSpacing: 0.05em
  code:
    fontFamily: JetBrains Mono
    fontSize: 14px
    fontWeight: '400'
    lineHeight: 22px
rounded:
  sm: 0.125rem
  DEFAULT: 0.25rem
  md: 0.375rem
  lg: 0.5rem
  xl: 0.75rem
  full: 9999px
spacing:
  unit: 4px
  gutter: 16px
  sidebar-width: 280px
  max-content-width: 1200px
  panel-padding: 24px
  touch-target: 44px
---

## Brand & Style

This design system is engineered for a **Professional/Modern** technical environment. It prioritizes clarity, data density, and a "developer-first" utility. The aesthetic is strictly flat, avoiding heavy shadows and skeuomorphic elements in favor of a structured, modular grid that feels like a high-performance workbench for information.

The design philosophy is built on **Modular Minimalism**:
*   **Precision:** High information density without visual clutter.
*   **Authenticity:** Using raw data (metadata, latency, file types) as a primary visual element.
*   **Structure:** Clear visual boundaries using subtle borders and tonal shifts to organize complex hierarchies.
*   **Focus:** An unobtrusive UI that recedes into the background to highlight user-generated Markdown and code content.

## Colors

The palette is anchored in a high-contrast foundation for maximum legibility. 
*   **Primary (Deep Indigo):** Reserved for primary actions, focus states, and key navigational highlights.
*   **Secondary (Slate Gray):** Used for meta-information, inactive states, and supporting UI elements like icons or labels.
*   **Background (Soft Gray):** Provides a subtle "stage" for the application, reducing eye strain during long sessions.
*   **Surface (White):** Used for active panels, cards, and input areas to create clear contrast against the soft gray background.
*   **Semantic Colors:** Emerald and Amber are used sparingly for status indicators (Updated, Created, Warning) to ensure they retain their communicative power.

The design system uses a "Border-First" depth strategy where `#E2E8F0` is the standard separator between layout regions.

## Typography

The system utilizes **Inter** for all prose and navigational elements due to its exceptional legibility and neutral character. **JetBrains Mono** is introduced for technical metadata, tags, and code blocks to provide a distinct "data-driven" texture to the UI.

*   **Hierarchy:** High contrast in weight is used rather than extreme size shifts. Headlines use tighter letter spacing for a more compact, modern feel.
*   **Readability:** Body text uses a standard 1.5x line height to facilitate long-form reading in the Markdown viewer.
*   **Metadata:** Labels and tags are set in monospace to emphasize their role as structured data points (IDs, Timestamps, Latency).

## Layout & Spacing

This design system uses a **Fixed-Fluid Hybrid** layout. 
*   **Sidebar:** Fixed at 280px to accommodate the complex file tree and primary navigation. 
*   **Main Workspace:** Fluid, stretching to fill the remaining viewport, but capping Markdown content at 1200px for optimal line lengths.
*   **Grid:** A 12-column grid is used within panels for card layouts and metadata displays.
*   **Rhythm:** A base 4px unit (4/8/12/16/24/32) ensures consistent alignment. 24px is the standard container padding to provide "breathing room" in an otherwise data-dense interface.

**Breakpoints:**
*   **Desktop (1024px+):** Full 3-pane layout (Sidebar | Main | Metadata Panel).
*   **Tablet (768px - 1023px):** Metadata panel collapses into a drawer; Sidebar becomes toggleable.
*   **Mobile (<768px):** Stacked layout with a focus on the primary stream (Chat or Editor). Navigation moves to a bottom bar or top hamburger menu.

## Elevation & Depth

To maintain the professional, flat aesthetic, depth is communicated through **Tonal Layering** and **Low-Contrast Outlines** rather than shadows.

*   **Background Layer:** The bottom-most surface is Soft Gray (#F8FAFC).
*   **Surface Layer:** Primary interactive panels (Editor, Message Stream) are White (#FFFFFF) with a 1px border (#E2E8F0).
*   **Active Focus:** When an element is selected (e.g., an active file in the tree), it receives a subtle background tint of the Primary color at 5-8% opacity.
*   **No Shadows:** Standard cards and UI elements are completely flat. A very soft, diffused shadow (10% opacity, 4px blur) is permitted only for temporary floating overlays like search dropdowns or context menus.

## Shapes

The shape language is **Soft and Precise**. A 0.25rem (4px) base radius is used for all standard components to provide a modern feel that isn't overly organic or "bubbly."

*   **Buttons & Inputs:** Use the base 4px radius.
*   **Cards & Panels:** Use 8px (rounded-lg) for larger containers to clearly group information.
*   **Tags & Status Pills:** Use a full "Pill" radius for distinct categorization and visual variety.

## Components

### Navigation Sidebar
Constructed of a hierarchical **File Tree**. Use chevron icons for expand/collapse states. Active nodes use the Primary color for the label and a subtle background fill.

### Search Bars
Full-width input with a left-aligned search icon. Should use a persistent 1px border (#E2E8F0). Focus state uses a 2px Primary border with no glow/shadow. Include "Type-to-search" micro-copy and keyboard shortcuts (e.g., ⌘K).

### Cards (Memory Results)
Flat white containers with a subtle border. Headers should include the `label-md` monospace tags. Hover states should trigger a slightly darker border (#CBD5E1) rather than a shadow.

### Message Bubbles (Chat)
*   **User:** Right-aligned, primary color background with white text.
*   **Agent:** Left-aligned, soft gray background with text-primary.
*   **Thinking Process:** A collapsible nested block within Agent messages using the `code` typography style and a dashed left border.

### File Tree Icons
Minimalist, monochrome icons for PDF, MD, TXT, and Folder types. Color should only be used to denote status (e.g., a small green dot for "updated").

### Buttons
*   **Primary:** Solid Indigo background, White text.
*   **Secondary:** Ghost style (Transparent background, Slate border).
*   **Actionable Labels:** Monospace tags that act as filters when clicked.