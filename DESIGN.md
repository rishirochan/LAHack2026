---
name: Clarity
description: Practice out loud. See yourself clearly.
colors:
  navy-primary: "#243763"
  navy-interactive: "#1d2f52"
  navy-deep: "#162240"
  teal-conversation: "#0d5c6b"
  amber-free: "#b45309"
  cream-base: "#FAF7F0"
  cream-surface: "#FDFBF7"
  cream-border: "#EDE3CC"
  cream-subtle: "#F5EFE0"
  ink-primary: "#0f172a"
  ink-secondary: "#475569"
  ink-tertiary: "#94a3b8"
  destructive: "#f04438"
typography:
  display:
    fontFamily: "Lora, Georgia, serif"
    fontSize: "clamp(2rem, 5vw, 3.5rem)"
    fontWeight: 400
    lineHeight: 1.1
    letterSpacing: "-0.01em"
  headline:
    fontFamily: "Lora, Georgia, serif"
    fontSize: "clamp(1.375rem, 3vw, 1.875rem)"
    fontWeight: 400
    lineHeight: 1.25
    letterSpacing: "-0.005em"
  title:
    fontFamily: "Plus Jakarta Sans, system-ui, sans-serif"
    fontSize: "1rem"
    fontWeight: 600
    lineHeight: 1.4
    letterSpacing: "normal"
  body:
    fontFamily: "Plus Jakarta Sans, system-ui, sans-serif"
    fontSize: "0.9375rem"
    fontWeight: 400
    lineHeight: 1.65
    letterSpacing: "normal"
  label:
    fontFamily: "Plus Jakarta Sans, system-ui, sans-serif"
    fontSize: "0.6875rem"
    fontWeight: 500
    lineHeight: 1.4
    letterSpacing: "0.08em"
rounded:
  xs: "4px"
  sm: "6px"
  md: "8px"
  lg: "10px"
  xl: "14px"
  full: "9999px"
spacing:
  xs: "4px"
  sm: "8px"
  md: "16px"
  lg: "24px"
  xl: "40px"
  2xl: "64px"
components:
  button-primary:
    backgroundColor: "{colors.navy-primary}"
    textColor: "{colors.cream-surface}"
    rounded: "{rounded.md}"
    padding: "8px 20px"
  button-primary-hover:
    backgroundColor: "{colors.navy-interactive}"
  button-outline:
    backgroundColor: "transparent"
    textColor: "{colors.ink-primary}"
    rounded: "{rounded.md}"
    padding: "8px 20px"
  button-ghost:
    backgroundColor: "transparent"
    textColor: "{colors.ink-secondary}"
    rounded: "{rounded.md}"
    padding: "8px 12px"
  input-default:
    backgroundColor: "transparent"
    textColor: "{colors.ink-primary}"
    rounded: "{rounded.md}"
    padding: "8px 12px"
  card-default:
    backgroundColor: "{colors.cream-surface}"
    textColor: "{colors.ink-primary}"
    rounded: "{rounded.xl}"
    padding: "24px"
---

# Design System: Clarity

## 1. Overview

**Creative North Star: "The Quiet Coaching Room"**

Clarity lives in the space between a serious training environment and a considered, calm one. The visual system is designed for a person who is already focused — running drills before a high-stakes conversation. It should lower their cortisol, not compete for their attention. Every surface is stripped to what earns its presence: feedback is surfaced clearly, practice flows are immersive, and nothing decorates.

The typographic system grounds the interface in quiet authority. Lora carries headers with editorial warmth, never theatrical. Plus Jakarta Sans handles body and UI text with humanist confidence — slightly more expressive than a neutral sans, grounded enough to feel like a professional tool. The combination reads "considered" rather than "designed."

Color is restrained. The cream and warm-white backgrounds dominate; the navy is precise and confident; the mode accent colors (teal-blue for Conversation, amber for Free Speaking, navy for Emotion Sprint) distinguish contexts without decorating them. The accent rule is strict: color identifies, it doesn't embellish.

This system explicitly rejects: corporate HR interfaces with clinical whitespace and institutional blues; purple-gradient AI-product aesthetics; gamified progress with streaks, confetti, or badge rewards; anything that could be mistaken for a SaaS dashboard built to impress a demo audience rather than serve a practicing user.

**Key Characteristics:**
- Warm cream surface, not cold white
- Serif display type that reads as editorial calm, not academic formality
- Mode accent colors that identify context at a glance
- Flat-by-default elevation; shadow appears as functional state change only
- Spacing that varies deliberately — denser in analysis views, more open in practice flows

## 2. Colors: The Warm Signal Palette

Color strategy: Restrained. Tinted neutrals carry most surfaces; navy acts as the precise structural accent; mode colors identify practice contexts. No color is decorative.

### Primary
- **Coaching Navy** (`#243763`): The structural color. Used for primary buttons, active nav states, and focus rings. A deep, grounded blue — serious without being cold, authoritative without being corporate.
- **Interactive Navy** (`#2e4a82`): The hover and interactive state variant. Slightly lighter, signals responsiveness. Never used as a static fill.
- **Deep Navy** (`#162240`): Used sparingly for high-contrast text labels over light backgrounds where the full ink-primary feels too desaturated.

### Secondary
- **Deep Ocean Teal** (`#0d5c6b`): Identifies the Conversation practice mode. A deep, serious teal-blue — the color of focus and sustained attention. Deliberately darker than a standard teal to avoid the "wellness app" association.

### Tertiary
- **Warm Amber** (`#b45309`): Identifies the Free Speaking mode. A muted, ochre-adjacent amber — not the saturated yellow of attention-grabbing UI, but the warmth of measured energy.

### Neutral
- **Warm Cream Base** (`#FAF7F0`): The dominant application background. A cream that tilts warm — the visual equivalent of the calm environment Clarity is designed to create.
- **Cream Surface** (`#FDFBF7`): Cards, modals, sidebar background. Slightly lighter than the base, sufficient to distinguish layers without hard contrast.
- **Cream Subtle** (`#F5EFE0`): Hover states on interactive items, divider fills, tonal backgrounds for sections.
- **Cream Border** (`#EDE3CC`): All borders, dividers, section rules.
- **Ink Primary** (`#0f172a`): Body text and display text. A slate-navy that reads as near-black without the harshness of pure black.
- **Ink Secondary** (`#475569`): Secondary labels, metadata, timestamps.
- **Ink Tertiary** (`#94a3b8`): Placeholders, disabled states, decorative rules.
- **Destructive** (`#f04438`): Error states and destructive actions only.

**The One Accent Rule.** Navy, teal, and amber are semantic identifiers, not decorative fills. Combined, they cover less than 15% of any given screen. Use them to identify, not to enhance.

**The Cream Purity Rule.** Never apply a colored tint to the cream backgrounds. The warmth of `#FAF7F0` is the warmth of the brand. Don't layer gradients or colored overlays on top of it.

## 3. Typography: Lora + Plus Jakarta Sans

**Display Font:** Lora (with Georgia, serif as fallback)
**Body Font:** Plus Jakarta Sans (with system-ui, sans-serif as fallback)
**Import:** `https://fonts.googleapis.com/css2?family=Lora:ital,wght@0,400;0,500;0,600;0,700;1,400;1,500&family=Plus+Jakarta+Sans:wght@400;500;600;700&display=swap`

**Character:** Lora is a serif designed for screens — open letterforms, generous spacing, warm without being decorative. It reads as considered and trustworthy at headline sizes without the tightness of more condensed serifs. Plus Jakarta Sans is the working partner: humanist curves, confident at small sizes, never cold. Together they sit exactly where Clarity lives: precise but not clinical, warm but not casual.

### Hierarchy
- **Display** (400 weight, clamp 2rem–3.5rem, line-height 1.1, tracking -0.01em): Landing page hero, major session headlines. Lora. Rare — used where the user needs to orient, not scan.
- **Headline** (400 weight, clamp 1.375rem–1.875rem, line-height 1.25, tracking -0.005em): Page titles, section headers inside sessions, scorecard category headings. Lora. The primary voice of a screen.
- **Title** (600 weight, 1rem, line-height 1.4): Card headings, sidebar group labels, modal titles. Plus Jakarta Sans semibold.
- **Body** (400 weight, 0.9375rem, line-height 1.65, max 70ch): All reading content — feedback paragraphs, critique text, descriptions, instructions. Plus Jakarta Sans. Never exceed 70ch line length.
- **Label** (500 weight, 0.6875rem, line-height 1.4, tracking 0.08em, uppercase): Section dividers, metadata tags, status chips, nav sublabels. Plus Jakarta Sans. Uppercase with tracking — used sparingly as wayfinding.

**The Serif Gate Rule.** Lora is reserved for headlines and display text only. Never use it for body copy, labels, UI controls, or interactive elements. When in doubt, use Plus Jakarta Sans.

**The Weight Floor Rule.** Plus Jakarta Sans 400 is the minimum weight for any readable text. Never use 300 or below. The font's warmth lives in its standard weight; going lighter reads as precious, not refined.

## 4. Elevation

Clarity is flat by default. Surfaces are layered tonally — cream-base behind cream-surface behind cream-subtle — without shadows. The depth hierarchy is established by background value alone. No ambient shadows on static cards; no drop shadows on sidebar or header.

Shadows appear only as a state response: hover on interactive cards, open state on dropdowns, and focus elevation on overlaid dialogs. This keeps the surface calm at rest.

### Shadow Vocabulary
- **Hover Lift** (`0 2px 8px 0 rgba(15, 23, 42, 0.08)`): Applied to interactive practice-mode cards on hover only. Signals that the card is a navigation target, not a content container.
- **Popover** (`0 4px 20px 0 rgba(15, 23, 42, 0.12), 0 1px 3px 0 rgba(15, 23, 42, 0.06)`): Dropdowns, popovers, command palettes. Communicates that a layer has been raised above the document.
- **Dialog** (`0 8px 40px 0 rgba(15, 23, 42, 0.16)`): Full modals and sheets. The heaviest shadow in the system — signals full interruption of the current context.

**The Flat-By-Default Rule.** A static surface has no shadow. Shadows are responses to state — hover, open, or overlay — not decoration. If a shadow exists on a card at rest, it's wrong.

## 5. Components

### Buttons
Clean, confident, no border-radius theatrics. The shape communicates function, not personality.
- **Shape:** Gently rounded (8px). Matches the input and card system.
- **Primary:** Coaching Navy background (`#243763`), cream-surface text. Padding 8px 20px. Transitions background to Interactive Navy (`#2e4a82`) on hover over 150ms ease-out-quart. Focus ring: 3px navy/50% offset.
- **Secondary / Outline:** Transparent background, cream-border border, ink-primary text. Hover: cream-subtle fill.
- **Ghost:** No border, no background. Ink-secondary text. Hover: cream-subtle background. Used for tertiary actions inside sessions and in the sidebar.
- **Sizing:** Default `h-9` (36px), Large `h-10` (40px) for primary CTAs on landing and session launch. Icon-only buttons are square at their height.

### Cards / Containers
- **Corner Style:** Extra-rounded (14px) for practice mode selector cards; standard rounded (10px) for data containers and scorecard sections.
- **Background:** Cream-surface (`#FDFBF7`) on cream-base backgrounds.
- **Shadow Strategy:** No shadow at rest. Hover Lift on interactive/navigable cards only.
- **Border:** Cream-border (`#EDE3CC`) at 1px. Never use a colored side-stripe. A tinted background, a leading number, or a mode-color icon establishes identity.
- **Internal Padding:** 24px standard; 16px for compact data cards.

### Inputs / Fields
- **Style:** Transparent background, cream-border border (1px), 8px radius, 12px horizontal padding, 36px height.
- **Focus:** Border shifts to navy-interactive; 3px ring at navy-interactive/50% opacity. No glow, no blur.
- **Error:** Border destructive (`#f04438`); 3px ring at destructive/20%.
- **Disabled:** 50% opacity, pointer-events none.

### Navigation (Sidebar)
- **Layout:** Left sidebar, collapsible. Expanded at ~220px, collapsed to icon-only (~52px).
- **Background:** Cream-surface (`#FDFBF7`), border-right cream-border.
- **Typography:** Title weight (600, 0.875rem) for labels. Label weight (uppercase, tracked) for section dividers.
- **States:** Default — ink-secondary text. Hover — cream-subtle background. Active — cream-subtle background with a small navy-primary left indicator (1px only, not a stripe).
- **Section dividers:** Horizontal rules in cream-border. Section labels in Label style (ink-tertiary, uppercase, tracked). Nothing more.

### Mode Selector Cards (Signature Component)
The three practice modes — Emotion Sprint, Conversation, Free Speaking — are the primary navigation from the dashboard. Each is a full-width interactive card with a leading colored icon, a title, a description, and a hover lift.
- **Sprint icon/accent:** Navy (`#243763`)
- **Conversation icon/accent:** Deep Ocean Teal (`#0d5c6b`)
- **Free Speaking icon/accent:** Warm Amber (`#b45309`)
- The accent appears only on the icon. The card background stays cream-surface. Never apply the mode color as the card background. The color identifies; the card does not become the color.

### Score / Feedback Chips
Used in scorecards for metric scores (Good / Fair / Needs Work) and emotion labels.
- **Shape:** Full-radius pill (`9999px`). Padding: 2px 10px.
- **Style:** Tinted background derived from the score semantic (cream-subtle for neutral, navy tint for positive, destructive tint for critical). No colored border-only chips — always a tinted background.
- **Typography:** Label style (uppercase, 0.6875rem, 500 weight).

## 6. Do's and Don'ts

### Do:
- **Do** use Lora for all headlines and page titles. Let it set the editorial tone of the page before Plus Jakarta Sans handles everything functional.
- **Do** keep cream-base (`#FAF7F0`) as the dominant surface. The warmth of this color is the character of the brand.
- **Do** use the mode accent colors (navy, deep ocean teal, warm amber) exclusively on icons and small semantic labels that identify a practice context. Nowhere else.
- **Do** deepen shadows only in response to state: hover, open, or overlay. Flat at rest.
- **Do** let scorecard and feedback views breathe. Wider line-heights, more vertical space between sections — this is where the user reads and reflects.
- **Do** keep practice flows (recording, live session) distraction-free. Reduce nav chrome, increase content focus.
- **Do** cap all body text at 70ch line length.
- **Do** use uppercase Label typography for wayfinding only (section dividers, mode sub-labels). Never on interactive elements or body copy.

### Don't:
- **Don't** use Lora for body copy, UI controls, labels, or interactive elements. It is a headline font only.
- **Don't** apply purple, violet, or gradient fills anywhere in the UI. Clarity is not a purple-gradient AI startup.
- **Don't** add streaks, badges, confetti, or gamified progress indicators. Clarity tracks progress — it does not celebrate it with animation rewards.
- **Don't** use colored side-stripe borders (border-left or border-right greater than 1px as a colored accent). Rewrite with a tinted background or a leading icon.
- **Don't** apply gradient text (background-clip: text with a gradient). Use a solid color. Emphasis is weight, not spectacle.
- **Don't** use glassmorphism or backdrop-blur decoratively. Not on cards, not on modals, not on the sidebar.
- **Don't** use the hero-metric template: a large number, a small label, and a gradient accent. It reads as SaaS demo UI — the opposite of evidence-based coaching.
- **Don't** design identical card grids: same-sized cards, icon + heading + paragraph, repeated. Use the mode selector pattern with meaningful differentiation.
- **Don't** apply neon accents, high-chroma brights, or dark backgrounds. Clarity is a calm, light-surface product. Dark mode is not designed here.
- **Don't** let the cream backgrounds be mistaken for white. If you reach for `#ffffff`, stop — use `#FDFBF7` instead.
- **Don't** use Inter or Playfair Display. These are the replaced fonts. Plus Jakarta Sans is the body font; Lora is the display font.
