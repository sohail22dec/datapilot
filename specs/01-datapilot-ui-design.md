# DataPilot — Product UI Specification

## 1. Purpose

DataPilot is a minimalist, AI-powered business data analytics workspace. The user interacts with their company and database metrics through a conversational interface, asking natural-language analytics questions such as:

- "What was our revenue last month?"
- "How many users signed up this month?"
- "Top 5 products by revenue"
- "Revenue by country"
- "Compare revenue with last month"

---

## 2. Primary Design Goals

1. **Minimal, Focused & Professional**: An uncluttered B2B workspace where data and conversation take center stage.
2. **Soft Charcoal Dark Theme**: Comfortable, low-glare dark surfaces with crisp typographic contrast.
3. **Warm Golden Yellow Accent**: Signature brand yellow (`#FEC50B` / `#F4B900`) used selectively for primary actions, active highlights, user bubbles, and brand identity.
4. **Distraction-Free Workspace**: Seamless canvas with no superfluous header bars, dividing lines, or unnecessary dashboard widgets.
5. **Toggleable Sidebar**: Smooth collapsible navigation allowing full focus on data conversations.
6. **Streamlined Message Composer**: Compact input bar focused on keyboard-first efficiency with zero clutter.
7. **shadcn/ui Primitives**: Built on accessible, robust UI primitives (`Button`, `Avatar`, `DropdownMenu`, `ScrollArea`, `Tooltip`).

---

## 3. Color System & Design Tokens

### 3.1 Color Palette

```text
Brand / Primary Accents
--primary:               #FEC50B (Warm Golden Yellow)
--primary-hover:         #F4B900
--primary-soft:          #383115 (Active conversation highlight)
--primary-bubble:        #FEC50B (User message bubble)

Dark Surfaces & Backgrounds
--background:            #181A20 (Main workspace canvas)
--surface-sidebar:       #1E222B (Sidebar background)
--surface-card:          #242834 (Assistant response card & composer)
--surface-hover:         #282E3A (Interactive item hover)

Borders & Dividers
--border:                #2E3444 (Sidebar border)
--border-card:           #323849 (Card & composer border)
--border-subtle:         #272C3A (Subtle separators)

Typography & Text
--text-primary:          #F1F5F9 (Primary headings and message text)
--text-white:            #FFFFFF (Bold metric highlights)
--text-secondary:        #CBD5E1 (Sidebar inactive labels)
--text-muted:            #94A3B8 (Placeholders, secondary icons)
--text-user-bubble:      #09090B (Dark charcoal text on yellow bubble)
```

---

## 4. Brand & Logo Specification

### 4.1 Concept: Minimalist Pilot Delta / Flight Vector

The DataPilot identity combines **Data Intelligence** and **Aerodynamic Navigation**.

- **Icon**: A faceted, forward-swept stealth flight delta vector with dual-tone wings and a central flight core accent.
- **Badge Container**: Rounded squircle container with a warm vertical gradient (`#FFCF25` → `#F5B800`) and dark silhouette geometry (`#0E1117`).
- **Wordmark**: `DataPilot` in bold sans-serif, crisp white text (`#FFFFFF`) with tight tracking.

### 4.2 Assets
- Component: `frontend/components/brand/DataPilotLogo.tsx`
- Vector Mark: `frontend/public/brand/datapilot-mark.svg`

---

## 5. Sidebar Specification

### 5.1 Structure & Layout
- **Width**: `320px` fixed desktop width (collapsible / toggleable).
- **Surface**: `#1E222B` with right border `#2E3444`.

### 5.2 Header & Actions
1. **Brand**: Top left with `DataPilot` logo and icon.
2. **Toggle Button**: Top right ghost button (`PanelLeftClose`) to collapse the sidebar.
3. **New Chat Button**:
   - Primary yellow background (`#FEC50B`), text `#111827`, font-semibold.
   - Icon: `+` (`Plus` icon).
   - Label: `New Chat`.

### 5.3 Conversation List
- Flat scrollable list powered by shadcn `ScrollArea` (no `Today`, `Yesterday`, or date group headers).
- **Active Conversation Item**:
  - Background: `#383115` with border `#FEC50B`/40.
  - Text: White font-medium.
- **Inactive Conversation Item**:
  - Background: Transparent (hover: `#282E3A`).
  - Text: `#CBD5E1` (hover: white).
- **Clean Format**: Displays clean conversation titles with full container width (`truncate flex-1`). No timestamps in the list.
- **Actions**: Hover reveal `Delete` trash icon for quick removal.

### 5.4 User Profile
- Anchored at the bottom of the sidebar.
- Displays user avatar and name: **Sohel Islam** (no "Admin" label).
- Interactive trigger opening a shadcn `DropdownMenu` with:
  - Account Profile Details
  - Settings
  - Sign out

---

## 6. Chat Workspace

### 6.1 Layout & Canvas
- Full remaining viewport with `#181A20` dark background.
- Clean canvas with **no top header bar or dividing horizontal line**.
- **Floating Sidebar Toggle**: When the sidebar is collapsed, a compact floating button appears in the top-left corner (`absolute top-4 left-4`) to reopen it.

### 6.2 Message Feed
Messages render chronologically with smooth auto-scroll to latest response:

1. **User Message**:
   - Aligned to the **right**.
   - Bubble: Vibrant warm golden yellow (`#FEC50B`), dark text (`#09090B`), rounded-2xl with top-right taper (`rounded-tr-xs`).
   - Avatar: User initials/photo avatar (`SI`) on the right.
2. **Assistant Message**:
   - Aligned to the **left**.
   - Avatar: Yellow DataPilot Delta icon badge on the left.
   - Card: Surface `#242834`, thin border `#323849`, rounded-2xl with top-left taper (`rounded-tl-xs`).
   - Content: Structured markdown support with bold metric highlighting (`$512,430`), bullet points, and clean typography.
3. **Loading Indicator**:
   - Displays when query is running: Pilot Delta icon avatar + 3-dot pulsating amber animation in a response card.
4. **Empty State**:
   - When no messages exist, displays the DataPilot Delta badge and a clean welcome prompt: *"Ask anything about your data"*.

---

## 7. Streamlined Composer

### 7.1 Layout & Dimensions
- Anchored near the bottom with comfortable horizontal padding (`max-w-3xl mx-auto mb-6`).
- Sleek dark surface (`#242834`) with border `#323849` and focus ring (`#FEC50B`/30).

### 7.2 Input & Controls
- **Input Area**: Auto-expanding single/multiline textarea with placeholder *"Ask anything about your data..."*.
- **No Clutter**: "Add filter" and "Attachment" buttons are removed for a clean keyboard-first interface.
- **Send Button**: Compact square rounded button (`#FEC50B`), dark paper plane icon (`Send`), disabled state (`#333948`).

### 7.3 Keyboard Shortcuts
- `Enter`: Submit and send message.
- `Ctrl + Enter` (or `Cmd + Enter`): Insert a new line in multiline queries.

---

## 8. Technical Architecture & Component Tree

```text
DataPilot Frontend (Next.js App Router, React 19, TypeScript, Tailwind CSS v4)
│
├── app/
│   ├── globals.css          # Color tokens, dark theme variables, custom scrollbars
│   ├── layout.tsx           # Root metadata & typography
│   └── page.tsx             # Application state, chat handlers, API integration
│
├── components/
│   ├── brand/
│   │   └── DataPilotLogo.tsx    # Pilot Delta SVG mark & wordmark
│   ├── sidebar/
│   │   └── Sidebar.tsx          # Toggleable sidebar with ScrollArea & DropdownMenu
│   ├── workspace/
│   │   ├── ChatWorkspace.tsx    # Message feed canvas & empty/loading states
│   │   ├── UserMessage.tsx      # User yellow bubble & avatar
│   │   ├── AssistantMessage.tsx # Assistant dark card & formatted metrics
│   │   └── ChatComposer.tsx     # Compact keyboard-first input & send button
│   ├── common/
│   │   └── UserAvatar.tsx       # Radix Avatar wrapper
│   └── ui/                      # shadcn/ui primitives
│       ├── button.tsx
│       ├── avatar.tsx
│       ├── dropdown-menu.tsx
│       ├── scroll-area.tsx
│       └── tooltip.tsx
│
└── types/
    └── chat.ts                  # TypeScript models (Message, Conversation, UserProfile)
```

---

## 9. Backend Integration

- **Endpoint**: `POST http://localhost:8000/api/chat`
- **Request Payload**: `{ "message": "<user query>" }`
- **Response Payload**: `{ "response": "<ai response text>", "model": "gemini-2.5-flash" }`
- **Error Handling**: Graceful network error handling with fallback connectivity notification.