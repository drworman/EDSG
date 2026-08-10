# Themes and branding

EDSG shares one appearance setting between the organizer and participant
builds, and applies it to both the interface and the reports. Configure it
once in **Options → Preferences**.

Settings live in a single file, so both binaries pick up the same choices:

| Platform | Location |
|---|---|
| Windows | `%APPDATA%\EDSG\settings.json` |
| macOS | `~/Library/Application Support/EDSG/settings.json` |
| Linux | `~/.config/edsg/settings.json` |

## Themes

Seven palettes, matching ED Linux Dash so the two tools look like a set:

| Theme | Accent |
|---|---|
| Elite Orange (default) | `#e07b20` |
| Green | `#00aa44` |
| Blue | `#3d8fd4` |
| Purple | `#9b59b6` |
| Red | `#cc3333` |
| Yellow | `#d4a017` |
| Light | `#005faa` on a pale background |

### Custom colours

Any of the eleven colours can be overridden in Preferences, with a picker or
by typing a hex value. Changes preview live; **Cancel** puts back what you
had. **Reset to theme defaults** clears every override.

Three further colours are **derived rather than chosen**: the table header
background, the header text, and the alternating row tint. Header text is
picked for contrast against its own background, so a custom accent cannot
produce an unreadable table — the previous hand-picked values were the
reason report headers were hard to read at all.

Overrides are stored per colour, not as a whole palette, so switching theme
afterwards keeps only what you actually changed.

## Squadron branding

**Preferences → Squadron branding** puts your identity at the top left of
every report.

| Field | Notes |
|---|---|
| Name | e.g. `Mining and Logistics, Ltd.` |
| Tag | e.g. `MALL`, rendered as `Name [TAG]` |
| Contacts | Up to four: Discord, email, website, Inara, other |
| Logo | PNG, JPEG, GIF or BMP, under 2 MB |

Leave it all blank for unbranded reports; the block is omitted entirely
rather than left as an empty space.

### About the logo

The logo is embedded directly in the HTML report as a data URI, so the file
stays self-contained when it is mailed or uploaded. That is also why there
is a size limit — a multi-megabyte logo defeats the point.

**SVG is not supported.** ReportLab cannot draw it, and a logo that appears
in the HTML but not the PDF is worse than one that appears in neither.

A missing or unreadable logo is skipped silently: moving the image must not
stop a report generating.

## What each format does with the theme

| Format | Behaviour |
|---|---|
| HTML | Full theme, self-contained, with a print stylesheet that switches to black on white |
| PDF | Prints on white whatever the theme, using the accent for headings and rules. A dark report wastes toner and reads badly on paper. A very light accent is darkened until it carries against the page. |
| Markdown | Branding as a heading; colours do not apply |
| JSON | Records the branding so a bot or site can reproduce the header |

## Where files are saved

Issuing an invitation creates a workspace beside the binary:

```
EDSG-Organizer(.exe)
Events/
└── Summer Mining Drive/
    ├── invitation/     the .edsgi you send out
    ├── submissions/    put the .edsgs files you receive here
    └── standings/      reports are written here
```

The organizer binary treats its own folder as the root, so an executable on a
memory stick or in a synced folder carries its events with it. Running from
source uses the current working directory instead, since a source tree is not
where anyone wants their event data. `EDSG_HOME` overrides both.

Event names are sanitised for the filesystem — `Test Event #1` becomes
`Test Event -1`, and Windows device names such as `CON` are prefixed — so a
name that reads well in the report cannot produce a folder that will not
create.
