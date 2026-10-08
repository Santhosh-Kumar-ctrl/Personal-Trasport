# UI.md — Design instructions for AI models

> **Paste this whole file into the prompt** (or attach it) whenever you ask an AI model to build or change
> a page, screen, dialog, sheet or widget in the Flutter app (`frontend/`). The model must follow it
> exactly. It describes the existing "Transit signage" design system so new UI looks the same as the rest of the app.
>
> Source of truth in code: `frontend/lib/design/` (`tokens.dart`, `theme.dart`, `widgets/`, `README.md`).
> Reference renders: `frontend/test/screenshots/*.png`. If this file and the code disagree, the code wins.
> When you change the design system, update this file too.

---

## 1. The idea in one paragraph

The app is a college bus transit system used by **students**, **drivers** and the **transport office (admin)**.
It must look like a **transit authority's product, not a SaaS template**. Every visual comes from real
wayfinding: enamel road and station signs, metro line maps, dark departure boards with amber LED figures,
bus number plates, punched paper tickets. It's flat, uses ruled lines, colour carries meaning, and the type is set like a sign.

---

## 2. Hard rules (non-negotiable)

1. **Import only `design/design.dart`** for visuals:
   `import '../../../design/design.dart';` (adjust depth). It exports tokens, theme and all signature widgets.
2. **Never hard-code colours, font sizes, font families, radii or spacing** in screens. Use
   `TransitColors.*`, `TransitType.*`, `Space.*`, `Radii.*`. Write no `Color(0x…)`, no `Colors.blue`, no `fontSize: 14` on a fresh `TextStyle`.
   (`Colors.transparent` is fine. Adjust a token with `.copyWith(...)` / `.withValues(alpha: ...)`.)
3. **Colour means something:**
   - `late` (red) = delay, over capacity, cancelled, destructive. `go` (green) = on time, boarded, arrived, success.
     `caution` (amber, **always with `ink` text**) = nearly full, warning, needs a check.
   - Never use status colours decoratively.
   - **Route colours are identity only** (badge, line, side band). Never use a route colour to show status.
   - `led` amber is **only** for live figures (expected times, delays on dark boards) and focus rings.
4. **No shadows, no gradients, no elevation.** Separate content with `Divider`s (rules), left
   coloured edges and background steps (`enamel` → `enamelDeep` / `white`). Floating cards are out.
5. **Radius is 4px** (`Radii.signAll` / `Radii.sign`) everywhere. No pills and no large rounded corners.
6. **Typeface is Overpass** (bundled, 400/600/800) via `TransitType`. Use `TransitType.figure` or `display`
   (tabular figures) for any number that should line up: times, counts, codes.
7. **Sentence case for all labels.** No ALL-CAPS eyebrows, no Title Case Buttons.
8. **Works at 360px wide** with a 16px gutter (`Space.gutter`). Check for overflow on phones.
9. **Motion:** the only orchestrated animation is the `TicketStub` stamp. Otherwise use only functional progress
   (loading bars, QR countdown). Respect `MediaQuery.disableAnimations`.
10. **Banned:** gradients, glassmorphism, purple/violet accents, rounded card grids with drop shadows, emoji,
    all-caps labels, `→` arrows in button text, `Card` with elevation, `FloatingActionButton`,
    `ElevatedButton`/`FilledButton`/`OutlinedButton`, `Chip`, default `AppBar`, and unstyled Material widgets.

---

## 3. Tokens

### Colours: `TransitColors`
| Token | Hex | Use (and only this) |
|---|---|---|
| `enamel` | `#EEF1F3` | Page background (light screens) |
| `enamelDeep` | `#E1E6EA` | Grouped surfaces, stripes, disabled button bg, "own" message bubble |
| `white` | `#FFFFFF` | Raised content plates (notices, tickets, inputs, bottom bar) |
| `signBlue` | `#123E63` | Structural headers/panels, primary buttons, info tone. Always white text on it |
| `signBlueDeep` | `#0C2C47` | Admin nav rail / admin phone top strip |
| `board` | `#17212B` | Dark departure-board surfaces, all driver screens |
| `boardLine` | `#2A3743` | Rules / empty seats on `board` |
| `led` | `#FFB81C` | Live figures on dark boards, active nav on dark, focus rim |
| `ink` | `#1B2733` | Primary text, quiet button border, selected choice fill |
| `inkSoft` | `#52606D` | Secondary text, captions, metadata |
| `rule` | `#C5CDD4` | Dividers, idle input borders, perforations |
| `late` | `#D7261E` | Delay / over capacity / cancelled / error / danger |
| `go` | `#1C8A4B` | On time / boarded / arrived / success |
| `caution` | `#F2A900` | Nearly full / warning (text on it is `ink`) |

Helpers: `TransitColors.parseHex('#1E88E5')` turns a route hex from the API into a colour.
`TransitColors.onRoute(color)` gives readable text (ink or white) for a route colour.

On dark (`board`) surfaces, text is `white`, secondary text is `white.withValues(alpha: 0.55–0.62)`,
and dimmed content is about 0.35–0.45 alpha.

### Type: `TransitType` (Overpass, ratio ≈ 1.25)
| Style | Size / weight | Use |
|---|---|---|
| `display` | 44 / 800, tabular | Hero figures (big countdowns, ETAs) |
| `title` | 28 / 800 | Screen titles (in `SignHeader`), sheet titles |
| `heading` | 20 / 800 | Section headings, dialog titles, notice titles |
| `subheading` | 16 / 600 | List row titles (often `.copyWith(fontWeight: FontWeight.w800)`), nav labels |
| `body` | 15 / 400 | Paragraphs, descriptions |
| `small` | 13 / 400 | Metadata, captions, timestamps, tags |
| `figure` | 18 / 800, tabular | Times, counts, route codes in rows |
| `button` | 17 / 800 | Button labels (applied by `SignButton`) |

Change only colour/weight/size with `.copyWith(...)` and keep the family.

### Spacing: `Space`
`xs 4` · `s 8` · `m 12` · `l 16` · `xl 24` · `xxl 32` · `gutter 16` (phone side margin).
Use these for every `SizedBox`, `EdgeInsets` and gap. One-off values (2px between title and subtitle,
fixed column widths in tables) are fine when they match what the existing code does.

### Shape: `Radii`
`Radii.sign` = `Radius.circular(4)`; `Radii.signAll` = `BorderRadius.all(Radii.sign)`.

---

## 4. Signature widgets (use these before building anything new)

| Widget | Use it for | Key params |
|---|---|---|
| `SignHeader` | **Top of almost every screen.** Sign-blue panel, white title, safe-area aware | `title`, `subtitle`, `leading` (back button), `trailing` (action), `color` (`TransitColors.board` on driver screens), `bottom` |
| `AsyncBody<T>` | Wrap every `AsyncValue` (Riverpod) body: thin progress bar while loading, `SignNotice` on error, keeps old data while refreshing | `value`, `builder`, `onRetry`, `onDark` |
| `SignNotice` | Empty / error / info states: white plate with a 6px left edge, plain words, at most one action | `title`, `body`, `actionLabel`, `onAction`, `edge` (`late` for errors, default `signBlue`) |
| `SignButton` | **All prominent actions.** Flat, 52px tall, LED focus rim, built-in busy spinner | `label`, `onPressed`, `kind` (`primary`, `go`, `danger`, `quiet`, `onDark`), `icon`, `expand`, `height`, `busy` |
| `StatusPlate` | Small status label (Open, Late 6 min, Full…) | `text`, `tone` (`Tone.late/go/caution/info/neutral`), `large` |
| `RouteBadge` | Square route tile with the route code in route colour | `code`, `color`, `size`, `rim: true` on dark panels |
| `NumberPlate` | Bus registration drawn as a plate (`TN 09 AB 1401`) | `registration`, `dense` |
| `LineDiagram` + `LineStop` | Vertical metro-style route map: passed stops grey, bus marker, "You" roundel, square campus terminus, struck-through scheduled times | `stops`, `color`, `showBus`, `onDark`, `trailingFor`. **This is the app's memorable element, so give it room** |
| `DepartureRow` | One row of the dark departure board (wide row or stacked on phones) | route, headline, detail, registration, scheduled/expected, status, seats |
| `SeatBlocks` | Occupancy as a top-down seat plan (2 + aisle + 2), red past capacity | `taken`, `capacity`, `onDark`, `cell` |
| `TicketStub` | Boarding receipt with the single "Boarded" stamp animation | route, registration, time, message, `onRoute` |

Module-level reusable widget already in the codebase:
- `Choice` (`modules/reports/widgets/choice.dart`): selectable option tile, ink-filled when selected and outlined otherwise.
  Use it (or move it into `design/widgets/` if a second module needs it) instead of Material `ChoiceChip`.

If you need a **new reusable visual**, add it to `frontend/lib/design/widgets/`, export it from
`design/design.dart`, ground it in a real transit/signage object, and document it in
`frontend/lib/design/README.md` and in this file.

---

## 5. Page structure (copy these skeletons)

### 5.1 Standard screen (student / admin, light)
Screens live in `frontend/lib/modules/<module>/screens/`. Inside a role shell, a screen returns a
`Column` and **not** its own `Scaffold`/`AppBar`. The shell provides the scaffold and navigation.

```dart
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import '../../../core/format.dart';
import '../../../design/design.dart';
import '../data/things_api.dart';

/// Student: what this screen is for, from the user's side.
class ThingsScreen extends ConsumerWidget {
  const ThingsScreen({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final things = ref.watch(thingsProvider);
    return Column(
      children: [
        SignHeader(
          title: 'Things',
          subtitle: 'One plain sentence of context',
          trailing: TextButton.icon(
            style: TextButton.styleFrom(foregroundColor: TransitColors.white),
            onPressed: () => context.go('/student/things/new'),
            icon: const Icon(Icons.add),
            label: const Text('New'),
          ),
        ),
        Expanded(
          child: AsyncBody(
            value: things,
            onRetry: () => ref.invalidate(thingsProvider),
            builder: (list) => list.isEmpty
                ? SignNotice(
                    title: 'No things yet',
                    body: 'Say what this list is for and how to fill it.',
                    actionLabel: 'Add a thing',
                    onAction: () => context.go('/student/things/new'),
                  )
                : RefreshIndicator(
                    onRefresh: () async => ref.invalidate(thingsProvider),
                    child: ListView.separated(
                      padding: const EdgeInsets.all(Space.gutter),
                      itemCount: list.length,
                      separatorBuilder: (_, _) => const Divider(),
                      itemBuilder: (_, i) => _Row(thing: list[i]),
                    ),
                  ),
          ),
        ),
      ],
    );
  }
}
```

### 5.2 Detail / sub-page
Use the same structure. Put a white back `IconButton` in `SignHeader.leading`, and navigate with
`context.go(...)` to the parent path (go_router). Don't use `Navigator.pop` for pages.

```dart
SignHeader(
  title: item.name,
  subtitle: item.summary,
  leading: IconButton(
    tooltip: 'Back',
    icon: const Icon(Icons.arrow_back, color: TransitColors.white),
    onPressed: () => context.go('/student/things'),
  ),
),
```

### 5.3 List rows
Rows sit on the enamel background, separated by `Divider()`. Don't wrap them in cards.

```dart
InkWell(
  onTap: ...,
  child: Padding(
    padding: const EdgeInsets.symmetric(vertical: Space.m),
    child: Row(
      children: [
        RouteBadge(code: r.routeCode, color: TransitColors.parseHex(r.routeColor), size: 36),
        const SizedBox(width: Space.m),
        Expanded(
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Text(r.title, style: TransitType.subheading.copyWith(fontWeight: FontWeight.w800)),
              Text(r.detail, maxLines: 1, overflow: TextOverflow.ellipsis,
                  style: TransitType.body.copyWith(color: TransitColors.inkSoft)),
              Text('Sent ${dayLabel(r.at)} ${hm(r.at)}',
                  style: TransitType.small.copyWith(color: TransitColors.inkSoft)),
            ],
          ),
        ),
        const SizedBox(width: Space.s),
        StatusPlate(label, tone: tone),
      ],
    ),
  ),
)
```

Map a domain status to `(label, Tone)` in one shared function (see `reportStatusPlate` in
`modules/reports/widgets/choice.dart`). Don't pick colours inline per screen.

### 5.4 Driver screens (dark)
Driver UI sits on `TransitColors.board`. Use `SignHeader(color: TransitColors.board, ...)`,
`AsyncBody(onDark: true, ...)`, `SignButton(kind: SignButtonKind.onDark)` for secondary actions
(`go` / `danger` for the main ones), `RouteBadge(rim: true)`, `LineDiagram(onDark: true)` and
`SeatBlocks(onDark: true)`. Live times are `led`. Drivers glance at the screen while working, so use big tap targets (≥ 52px buttons) and few words.

### 5.5 Admin (transport office) screens
These render inside `AdminShell`, which shows a sign-blue rail at ≥ 960px and a drawer below that. Screens must
also work on a phone. Use `LayoutBuilder` breakpoints like the existing code:
- `< 600`: stack row info above its actions.
- `< 900`: single column for editor and preview layouts.
- `>= 1180`: board + side panel.
Cap reading-width content (forms, dialogs) at 420–760px with `ConstrainedBox`.

### 5.6 Forms
- Use plain `TextField` / `TextFormField` / `DropdownButtonFormField` with `InputDecoration(labelText: ...)`.
  The theme already styles them (white fill, 4px radius, rule border, sign-blue focus, `late` error).
  Don't restyle them per screen.
- Labels are short and sentence case. Mark optional fields "(optional)" instead of marking required ones.
- Vertical rhythm is `SizedBox(height: Space.m)` between fields.
- Show an inline error under the fields: `Text(_error!, style: TransitType.body.copyWith(color: TransitColors.late))`.
- Submit with `SignButton(label: 'Send', expand: true, busy: _busy, onPressed: ready && !_busy ? _submit : null)`.
- Keep the state pattern: `var _busy = false; String? _error;` with try / `on ApiException catch (e) { _error = e.message; }`,
  then `if (mounted) setState(...)`.

### 5.7 Dialogs
Use `AlertDialog` (the theme makes it flat enamel with a 4px radius).
Title: `Text('Add person', style: TransitType.heading)`. Content: `SizedBox(width: 420, child: ...)`.
Actions: `TextButton` for cancel and `SignButton` (`primary` / `danger`) for the main action.
Return a result with `Navigator.pop(context, true)` and refresh the provider in the caller.

### 5.8 Bottom sheets
Use `showModalBottomSheet(context: ..., isScrollControlled: true, builder: ...)`. Pad with
`EdgeInsets.fromLTRB(Space.gutter, Space.xl, Space.gutter, MediaQuery.viewInsetsOf(context).bottom + Space.xl)`.
Start with a `TransitType.title` title and a one-line `inkSoft` body, then the inputs, then one `SignButton(expand: true)`.
Expose the sheet as a top-level function: `Future<void> showXyzSheet(BuildContext context, {...})`.

### 5.9 Feedback
- Use a snackbar for transient confirmations and errors on actions:
  `ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text('Logged. Hand the item in at the transport office.')))`.
  It's themed as a dark board strip.
- Use `SignNotice` for persistent states (empty, closed, not allowed).
- Use `AsyncBody` for loading. Don't add a centred `CircularProgressIndicator` to pages.

### 5.10 Accent edges and message plates
To set a block apart, use a white or `enamelDeep` plate with a **coloured left border** (5–6px), not a shadow:

```dart
Container(
  padding: const EdgeInsets.all(Space.m),
  decoration: BoxDecoration(
    color: TransitColors.white,
    borderRadius: Radii.signAll,
    border: Border(left: BorderSide(color: TransitColors.signBlue, width: 5)),
  ),
  child: ...,
)
```

### 5.11 Navigation & routing
Routes are registered **only** in `frontend/lib/app.dart` inside the right role `ShellRoute`
(`/student/...`, `/driver/...`, `/admin/...`). To add a tab, add a `NavItem` to the right shell in
`frontend/lib/shell/role_shells.dart`. Keep phone bottom bars short (students have 4 tabs and drivers have 2 today). Prefer a sub-page
over a fifth tab. Admin pages go in the rail list. Use outlined Material icons
(`Icons.*_outlined`) to match.

---

## 6. Formatting & copy

- Times and dates come from `core/format.dart`: `hm(t)` (24h `HH:mm`), `dayLabel(d)`, `relative(t)`,
  `delayLabel(minutes)`. Don't call `intl` directly in screens.
- A late time shows the **expected** time prominently (`led` on dark, `late` on light) with the
  **scheduled** time struck through in `inkSoft` underneath.
- Bus registrations always render with `NumberPlate`. Route codes always render with `RouteBadge`.
- **Write copy from the user's side** in short plain sentences, like a sign:
  "Scan to board", "Running late", "Tell riders", "Report a problem", "No reports yet".
- Errors say **what happened and what to do**: "Couldn't load this" + reason + "Try again".
- Use the middle dot `·` to join metadata ("Transport office · Today 08:14").
- No emoji, no exclamation marks, no "Oops!", no `→` in buttons.

---

## 7. Accessibility

- Text contrast: white on `signBlue`/`board`/`late`/`go`, and `ink` on `caution`/`enamel`/`white`. Don't put white text on `caution`.
- Every `IconButton` gets a `tooltip`. Custom-painted widgets get a `Semantics(label: ...)`.
- Minimum tap target is 44px. Primary actions are 52px (`SignButton` default).
- Keyboard focus is shown by the LED rim (built into `SignButton`). Don't remove focus styling.
- Don't rely on colour alone. Every status colour comes with a word (`StatusPlate` text).

---

## 8. Checklist before you finish

- [ ] Imports `design/design.dart`; no raw `Color(...)`, `Colors.<hue>`, ad-hoc `TextStyle(fontSize:)`, or `fontFamily`.
- [ ] Screen starts with `SignHeader`; async data goes through `AsyncBody`; empty state is a `SignNotice`.
- [ ] Buttons are `SignButton` (or a themed `TextButton` for low-emphasis/header actions).
- [ ] Status shown with `StatusPlate` + correct `Tone`; route identity with `RouteBadge`; buses with `NumberPlate`.
- [ ] No shadows, gradients, elevation, pills, all-caps, emoji, purple.
- [ ] All spacing from `Space`, all radii `Radii.signAll`.
- [ ] Renders without overflow at 360px wide; admin screens also checked at ≥ 960px.
- [ ] Driver screens use the dark `board` variants.
- [ ] Copy is sentence case, from the user's side, errors say what to do next.
- [ ] Animations limited to functional progress; `disableAnimations` respected.
- [ ] Route registered in `app.dart`; tab (if any) added in `role_shells.dart`.
- [ ] If a screenshot test exists for the area, regenerate: 
      `flutter test test/screenshots_test.dart --run-skipped --update-goldens` and eyeball `test/screenshots/`.
