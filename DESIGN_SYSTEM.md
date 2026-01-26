# iOS-like Premium Design System

## Overview

This design system provides a modern, professional iOS-like interface with light and dark mode support.

## Color Palette

### Light Mode (Default)
- **Background**: `#f5f5f7` (base), `#ffffff` (surface), `#fafafa` (elevated)
- **Text**: `#1d1d1f` (primary), `#6e6e73` (secondary), `#86868b` (muted)
- **Primary**: `#3b82f6` (professional blue)
- **Semantic**: `#10b981` (success), `#f59e0b` (warning), `#ef4444` (danger)

### Dark Mode
- **Background**: `#000000` (base), `#1c1c1e` (surface), `#2c2c2e` (elevated)
- **Text**: `#f5f5f7` (primary), `#aeaeb2` (secondary), `#8e8e93` (muted)
- **Primary**: `#0a84ff` (iOS blue)
- **Semantic**: `#30d158` (success), `#ff9f0a` (warning), `#ff453a` (danger)

## Typography

- **Font Stack**: `-apple-system, BlinkMacSystemFont, "SF Pro Display", "SF Pro Text", "Segoe UI", "Inter", sans-serif`
- **Headings**: 36px, 30px, 24px, 20px, 18px
- **Body**: 16px (base), 14px (small), 12px (xs)
- **Weights**: 300 (light), 400 (regular), 500 (medium), 600 (semibold), 700 (bold)

## Spacing (8pt grid)

`4px, 8px, 12px, 16px, 24px, 32px, 48px, 64px`

## Border Radius

- **Small**: 8px
- **Medium**: 10px (default for buttons/inputs)
- **Large**: 16px (cards)
- **Extra Large**: 20px
- **Full**: 999px (pills/badges)

## Components

### Buttons
- `.btn` - Base button
- `.btn-primary` - Primary action (blue gradient)
- `.btn-secondary` - Secondary action
- `.btn-tertiary` - Tertiary action
- `.btn-icon` - Icon-only button (40x40px)
- `.btn-sm` / `.btn-lg` - Size variants

### Input Fields
- `.input` - Text input
- `.select` - Select dropdown
- `.textarea` - Multi-line text
- Focus state: Blue border + subtle shadow

### Cards
- `.card` - Standard card with shadow
- `.glass-panel` - Glass morphism card (blur 20px)

### Badges
- `.badge` - Base badge (pill shape)
- `.badge-primary`, `.badge-success`, `.badge-warning`, `.badge-danger`

### Navigation
- `.nav-link` - Navigation link (pill shape when active)
- Active state: Blue gradient background

### Todo Items
- `.todo-item` - Todo container
- `.todo-checkbox` - Circular iOS-style checkbox
- `.todo-content` - Todo text and metadata
- `.todo-actions` - Action buttons

## Theme Switching

The design system supports dynamic theme switching:

```javascript
// Set theme
window.themeManager.setTheme('light'); // or 'dark'

// Toggle theme
window.themeManager.toggleTheme();

// Get current theme
const current = window.themeManager.getTheme();
```

Theme preference is persisted to `localStorage` and respects system preferences.

## Accessibility

- **WCAG 2.1 AA** compliant contrast ratios
- **Focus indicators** visible on all interactive elements
- **ARIA labels** on icon buttons and important elements
- **Keyboard navigation** fully supported
- **Screen reader** friendly with semantic HTML and ARIA attributes
- **Reduced motion** support via `prefers-reduced-motion`

## File Structure

```
static/
├── styles/
│   ├── design-system.css   # Core variables and base styles
│   ├── components.css      # Reusable UI components
│   ├── utilities.css       # Utility classes
│   └── animations.css      # Animations and transitions
├── js/
│   └── theme-switcher.js   # Theme toggle functionality
└── theme.css               # Legacy compatibility (merged with design system)
```

## Usage

Import the design system in your HTML:

```html
<!-- iOS-like Design System -->
<link href="/styles/design-system.css" rel="stylesheet" />
<link href="/styles/components.css" rel="stylesheet" />
<link href="/styles/utilities.css" rel="stylesheet" />
<link href="/styles/animations.css" rel="stylesheet" />

<!-- Theme Switcher -->
<script src="/js/theme-switcher.js"></script>
```

Add theme toggle button:

```html
<button type="button" id="themeToggle" class="btn btn-icon" aria-label="Toggle theme">
  <span class="material-icons-round theme-icon" data-theme-icon="light">dark_mode</span>
  <span class="material-icons-round theme-icon" data-theme-icon="dark">light_mode</span>
</button>
```

## CSS Variables

All design tokens are available as CSS variables:

```css
/* Colors */
var(--bg-base)
var(--text-primary)
var(--primary)
var(--success)

/* Spacing */
var(--space-4)

/* Shadows */
var(--shadow-md)

/* Transitions */
var(--duration-normal)
var(--ease-out)
```

## Migration Notes

The design system replaces the previous "Cyber-Zen" neon color scheme with a professional blue palette while maintaining all existing functionality. All Tailwind classes continue to work with the new colors.

Key changes:
- Neon cyan (`#00d4ff`) → Professional blue (`#3b82f6` light, `#0a84ff` dark)
- Ultraviolet (`#7000ff`) → Same professional blue for consistency
- Glass morphism reduced from 16px to 20px blur
- All shadows adjusted for iOS-like appearance
