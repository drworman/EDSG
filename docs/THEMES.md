# Themes and branding

EDSG shares one appearance setting between the organizer and participant
builds, and applies it to both the interface and the reports. Configure it
once in **Options → Preferences**.

Each binary stores its settings under a folder named for its role:

| Platform | Location |
|---|---|
| Windows | `%APPDATA%\EDSG\Organizer\settings.json` |
| macOS | `~/Library/Application Support/EDSG/Organizer/settings.json` |
| Linux | `~/.config/EDSG/Organizer/settings.json` |

Replace `Organizer` with `Participant` for the other build. They are kept
apart because the organizer file holds things the participant has no business
carrying — a signing identity participants have been told to trust, and the
squadron details below.

If you run both builds, set your theme in each. The trade is deliberate: one
shared file would mean a participant install carrying an organizer identity.

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

## What the organizer remembers

Beyond appearance, the organizer build keeps a few things so a squadron
running events regularly configures them once:

| Remembered | Set by | Reused as |
|---|---|---|
| Squadron ID and name | *Detect from my journals* on the Event tab | The default for every new event |
| Organizer name | Typed on the Event tab, saved when an invitation is issued | The default for every new event |
| Squadron branding | Preferences → Squadron branding | The header of every report |

Detecting again overwrites what was stored, so a commander who changes
squadron simply re-detects. Nothing here affects an event that has already
been issued: the squadron is baked into the signed invitation at that point.

The participant build stores none of this.

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

## Dialogs

The theme covers Qt's own windows too — file choosers in particular. Qt draws
their navigation arrows with its own dark pixmaps, which are close to
invisible on a dark background, so those buttons are given a raised surface
and a border under every theme.

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
Documents/EDSG/
└── Events/
    └── Summer Mining Drive/
        ├── 1 - Invitation/    the .edsgi you send out
        ├── 2 - Submissions/   put the .edsgs files you receive here
        └── 3 - Standings/     reports are written here
```

Events are your documents, so they live in your Documents folder. Writing
beside the executable is not a safe default: a binary in Program Files cannot
write to its own folder, and writing inside a signed macOS `.app` bundle
breaks its signature.

The subfolders are numbered so they list in the order you use them —
alphabetically, "standings" would sort between the other two.

Two escapes exist. Setting `EDSG_HOME` points the workspace anywhere. Dropping
an empty file named `EDSG-portable.txt` beside a frozen binary keeps events on
the same drive, which is what you want running EDSG from a memory stick.

Event names are sanitised for the filesystem — `Test Event #1` becomes
`Test Event -1`, and Windows device names such as `CON` are prefixed — so a
name that reads well in the report cannot produce a folder that will not
create.
