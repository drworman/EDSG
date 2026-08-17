# Organizer guide

Running an event from start to finish.

## Before you begin

You need **EDSG-Organizer**. Participants need **EDSG-Participant** — send them
the link to the Releases page rather than a copy of your organizer binary.

On first launch EDSG generates your signing identity and shows its
**fingerprint** on the *Issue invitation* tab:

```
AF87 76A3 1301 ADED 2280 54DC 7394 5532
```

**Publish this fingerprint somewhere your community already trusts** — pinned
in your squadron Discord, on your wiki, wherever people will look. It is how
participants confirm an invitation is really from you, and it is the only
defence against someone forging one in your name. It stays the same for every
event you run, so publish it once.

## 1 · Define the event

**Name and description** appear in the participant application and at the top
of every report. Write the description for someone deciding whether to take
part.

**Period.** Times are UTC, because journals record UTC. New events default to
`00:00:00` on the start date and `23:59:59` on the end date, so a period
covers whole days.

Click the hour, minute or second to change it — the calendar button only sets
the date. The **quick-set** buttons cover the common cases: whole day, this
month, this year.

Untick either bound to leave that end open — useful for "everything up to the
deadline" events.
Journal events outside the window are ignored entirely, so a participant with
five years of logs is scored only on the window.

**Who can take part.**

- *Open* — anyone with the invitation.
- *Restricted to my squadron* — click **Detect from my journals** and point
  EDSG at your own journal folder. It reads your logs, identifies the squadron
  you are currently in, and records its numeric ID. You never type an ID, and
  there is no way to typo one.

  Participants must show a join event for that squadron with no later leave,
  kick or disband. Someone who left mid-event is caught; someone who applied
  but never joined is caught.

  **You only do this once.** The detected squadron is remembered and offered
  as the default for every event you create afterwards. Detect again whenever
  it changes.

  If detection finds nothing, log into the game while in your squadron so a
  `SquadronStartup` event is written, then try again.

**Tie-break** decides equal point totals. Earliest submission rewards getting
results in promptly; alphabetical is the neutral option.

## 2 · Add criteria

One criterion per thing you are measuring. Each has a metric, optional
filters, and a points value. The full reference is in [CRITERIA.md](CRITERIA.md);
what follows is the judgement rather than the mechanics.

**Use caps.** Without one, a single high-volume category decides the event.
Mining tonnage and Powerplay merits run to five and six figures; bodies mapped
runs to hundreds. Left uncapped alongside each other, the merits criterion is
the only one that matters.

**Balance the units before the points.** Work out roughly what a committed
participant might achieve in each category over the period, then set points per
unit so the categories are worth comparable amounts. Credit-based measures need
very small values — `0.000001` gives one point per million credits.

**Be specific about location when it matters.** "Sell tritium" and "sell
tritium to our carrier" are very different events. For a specific fleet
carrier, filter on its market ID rather than its name: names change, callsigns
repeat, and the ID does not. Dock there yourself and read it from your journal,
or from `--cli inspect` on a submission that includes it.

**Label criteria for the standings table.** The label becomes a column heading
in the reports; keep it short.

The *Duplicate* button is the quickest way to build a set of similar criteria —
one per ore, say — then edit each copy.

**Commodity names are forgiving.** "Low Temperature Diamonds", "Low Temp.
Diamonds" and `$lowtemperaturediamond_name;` are the same commodity to EDSG,
and the field offers an autocomplete. Systems and stations are matched
loosely too, but not reconciled the same way — check those.

**Check your names.** A misspelled system or station scores zero in silence,
and once the invitation is signed there is no correcting it without reissuing
and asking everyone to rescan. The criterion editor has a **Check names
against Spansh** button for exactly this. It is advisory: Spansh does not know
every name, and being offline says nothing about your spelling, so EDSG never
blocks on it.

**Every criterion needs a Unit Cap.** It is what the criterion races for: the
total units it is worth across everybody, filled in the order the work
happened. Once full, later work earns nothing. The caps together decide what
the goal tiers are worth, so they are not optional. See [GOALS.md](GOALS.md).

**Minimum per CMDR** is separate and optional — a participation floor, below
which a commander scores nothing for that criterion.

## 3 · Rewards

Optional, and skippable for a plain leaderboard.

Goal tier thresholds are worked out from your criteria — you never type a
target. Untick the tiers you do not want and the rest rebalance.

Set **Maximum Reward Pool in Credits**, and choose how many leading
commanders share a bonus and how much of the pool it takes (10 and 25% by
default). Everything is then shared out in proportion to what each commander
contributed, so nobody can out-earn someone who did more.

Nothing is paid if the goal does not reach Tier 1. See [GOALS.md](GOALS.md).

## 4 · Issue the invitation

The *Readiness* panel lists anything blocking you. When it is clear, click
**Issue invitation**.

EDSG creates a workspace for the event beside the binary and offers to save
the invitation inside it:

```
Documents/EDSG/Events/Summer Mining Drive/
├── 1 - Invitation/
├── 2 - Submissions/
└── 3 - Standings/
```

All three folders are created together, and the *Close & publish* tab is
pointed at them, so there is nowhere left to guess. You can still save the
invitation elsewhere if you prefer.

Event names are sanitised for the filesystem — `Test Event #1` becomes
`Test Event -1` — so a name that reads well in a report cannot produce a
folder that will not create. `EDSG_HOME` overrides the workspace root.

**Your work is saved as you go.** The event is written to `event.edsgevent`
in its own folder whenever you change it, so closing the window loses
nothing. Reopen it with File → Open event draft, or by loading the `.edsgi`
on tab 4, which restores the whole event definition.

Send participants:

1. the `.edsgi` file,
2. your fingerprint,
3. a deadline for returning submissions.

Issuing moves the event to OPEN. You can issue again — to fix a mistake or add
a criterion — but anyone who already submitted against the old invitation will
be rejected at closing time, since their submission records which invitation it
came from. If you must reissue, tell everyone to rescan.

**Keep the `.edsgi` file.** You need it at closing time, and it is the easiest
way to restore the event definition if you rebuild your machine.

Use **File → Save event draft** to keep an editable `.edsgevent` copy. Drafts
are not signed and are for your own use.

## 5 · Collect submissions

Participants send back `.edsgs` files, each named for their Frontier ID.
Put them in the event's `submissions` folder.

**Check the preview as they arrive.** Selecting the submissions folder scores
every file immediately and fills the standings table, without closing the
event or writing anything. The line above the table reads *"Preview — 2
ranked, 0 would be rejected"*, and anything that would be rejected is listed
in the log with its reason.

This is the point at which a bad submission is worth finding. Closing is the
one irreversible action in the application, and a participant can still
rescan and resend beforehand. **Refresh preview** re-runs it after new files
land.

Treat that folder as personal data: it contains commander names, Frontier IDs
and play statistics. Do not publish the raw files.

If someone sends two submissions, the newer one wins automatically and the
older is listed as superseded. Nobody needs to keep track of that by hand.

## 5 · Close and publish

On the *Close & publish* tab, choose the submissions folder and — strongly
recommended — the `.edsgi` file you issued. Loading the invitation lets EDSG
reject submissions built from a different or forged one, and restores the
event definition if you are closing from a fresh install.

**Closing is permanent.** The event cannot be reopened and no further
invitations can be issued. EDSG asks for confirmation.

Choose an output folder and EDSG writes four reports:

| Format | Good for |
|---|---|
| `.md` | Pasting into Discord or a wiki |
| `.html` | Sharing a link, or printing; self-contained, no external assets |
| `.pdf` | Archiving and formal write-ups |
| `.json` | Feeding a bot, a spreadsheet, or a season-long tally |

**Keep the submissions folder.** *Regenerate reports* rebuilds all four at any
time, producing identical output. Without the submissions there is nothing to
regenerate from.

## Branding your reports

**Options → Preferences → Squadron branding** puts your squadron name, tag,
contact details and logo at the top left of every report. **Appearance** sets
the theme, which applies to both the interface and the generated reports.

Your squadron, your name and your branding are all remembered between events,
so this is configured once rather than at every event. The organizer build
keeps its settings in its own folder — `EDSG/Organizer/` under the
per-user configuration directory — separate from the participant build.
See [THEMES.md](THEMES.md).

## Reading the results

The standings table shows points per criterion with measured units beneath, so
you can see *why* someone placed where they did.

Below it, two sections worth reading before announcing anything:

- **Rejected submissions**, each with its reason — wrong event, failed
  signature, ineligible, superseded.
- **Submission audit**, listing per commander the journal events parsed, files
  read, generation time and signing fingerprint.

The audit exists because EDSG cannot verify that anyone's journals are genuine
— see [SECURITY.md](SECURITY.md). What it can do is show you the shape of each
submission. A commander reporting a huge total from four hundred journal events
when everyone else shows a hundred thousand is visible here. So is one whose
sample timestamps cluster implausibly.

## Troubleshooting

**"No commander could be identified in that directory."** Not a journal folder,
or it has no `Journal.*.log` files. On Linux the game lives inside a Proton or
Wine prefix; EDSG checks the usual paths automatically.

**"That directory contains journals for more than one commander."** Two
accounts share the folder. EDSG will not guess; separate them.

**A submission is rejected as "signed by a different key."** It was built from
a different invitation. Send the correct `.edsgi` and ask for a rescan.

**Everyone scored zero on one criterion.** Usually a filter that matches
nothing. Check the spelling of a system or station, and remember that filters
match substrings of both internal and localised names — so `massacre` works but
`Massacre Mission` may not.
