# API & UI Design System Specification

This specification defines the **Design System** covering both **REST API Standards** (data contracts, payload conventions, status codes, error handling) and **UI/Frontend Design Tokens** (color palettes, typography, glassmorphism, components) for the Novel Translation Ecosystem.

---

## 🌐 Part 1: REST API Design System

### 1. API Conventions & Naming Standards
- **Base URI Path**: `/api/v1`
- **Resource Naming**: Plural nouns (e.g., `/platforms`, `/models`, `/series`, `/chapters`, `/jobs`).
- **Casing Convention**:
  - **Request Body Payload**: Accepts both `camelCase` and `snake_case` through Pydantic field aliases.
  - **Response Payload**: Standardized on `snake_case` across all API responses.
- **Content Type**: `application/json` for requests and responses.

---

## 🎨 Part 2: Frontend & Web UI Design System

When developing administrative web interfaces, dashboards, or reader apps for the Novel Translation System, strictly adhere to this visual design system.

### 1. Color Tokens & Dark Theme Palette

The design aesthetic follows a modern **Deep Midnight Glassmorphism** theme built for comfortable extended reading and dashboard management.

```css
:root {
  /* Color Palette - Modern Midnight Aesthetic */
  --bg-primary: #0b0f19;         /* Deep Space Dark Background */
  --bg-surface: #111827;         /* Surface Card Fill */
  --bg-surface-glass: rgba(17, 24, 39, 0.75); /* Glassmorphism Backdrop */

  /* Accent Gradients */
  --primary-accent: #6366f1;     /* Indigo Primary */
  --primary-accent-hover: #4f46e5;
  --secondary-accent: #a855f7;   /* Cyber Purple */
  --gradient-brand: linear-gradient(135deg, #6366f1 0%, #a855f7 100%);
  --gradient-emerald: linear-gradient(135deg, #10b981 0%, #059669 100%);

  /* Text & Typography */
  --text-main: #f9fafb;          /* High contrast text */
  --text-muted: #9ca3af;         /* Muted secondary text */
  --text-subtle: #6b7280;        /* Metadata text */

  /* Borders & Dividers */
  --border-glass: rgba(255, 255, 255, 0.1);
  --border-subtle: rgba(255, 255, 255, 0.05);

  /* Status Colors */
  --status-pending: #f59e0b;     /* Amber */
  --status-processing: #3b82f6;  /* Blue */
  --status-completed: #10b981;   /* Emerald */
  --status-failed: #ef4444;      /* Rose Red */
}
```

### 2. Glassmorphism & Micro-Interactions

```css
/* Glassmorphism Card Style */
.glass-card {
  background: var(--bg-surface-glass);
  backdrop-filter: blur(16px);
  -webkit-backdrop-filter: blur(16px);
  border: 1px solid var(--border-glass);
  border-radius: 12px;
  box-shadow: 0 8px 32px 0 rgba(0, 0, 0, 0.37);
  transition: transform 0.2s ease, border-color 0.2s ease;
}

.glass-card:hover {
  border-color: rgba(99, 102, 241, 0.4);
  transform: translateY(-2px);
}

/* Vibrant Button Component */
.btn-primary {
  background: var(--gradient-brand);
  color: #ffffff;
  font-weight: 600;
  padding: 0.625rem 1.25rem;
  border-radius: 8px;
  border: none;
  cursor: pointer;
  box-shadow: 0 4px 14px 0 rgba(99, 102, 241, 0.39);
  transition: opacity 0.2s ease, transform 0.1s ease;
}

.btn-primary:hover {
  opacity: 0.92;
  transform: scale(1.02);
}
```

### 3. Responsive Typography & Layout

- **Font Family**: Primary UI font: `Inter`, `Roboto`, `system-ui`. Reading content font: `Outfit` or `Lora` (for clean novel reading experience).
- **Layout Container**: Max width `1400px` for dashboard; `800px` centered for reader views.
