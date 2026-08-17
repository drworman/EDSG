# Participant guide

Taking part in an event. The whole process is four steps and takes a couple of
minutes, most of it spent scanning.

## What you need

**EDSG-Participant** for your platform, and the `.edsgi` invitation file your
organizer sent you.

You do not need an account, an API key, or an internet connection. EDSG makes
no network connections at all.

## 1 · Open the invitation

Click **Open** and choose the `.edsgi` file. EDSG checks its signature before
showing you anything, and displays the event: who is running it, the period,
who may take part, and every criterion with its scoring rule.

It also shows the **fingerprint** of the key that signed it:

```
Signed by  AF87 76A3 1301 ADED 2280 54DC 7394 5532
```

**Compare this against the fingerprint your organizer published.** They should
have posted it somewhere you already trust — the squadron Discord, a wiki, a
forum thread. If the two do not match, stop and ask them about it. A forged
invitation will otherwise verify perfectly well, because the forger can sign
their own file; the fingerprint is what catches it.

If EDSG refuses the file outright, it has been modified since signing. Ask for
a fresh copy.

## 2 · Point EDSG at your journals

EDSG usually finds your journal folder by itself, including inside Steam
Proton and Wine prefixes on Linux. If it does, you will see your commander name
and Frontier ID confirmed in green.

Otherwise click **Browse**. The default locations are:

| Platform | Location |
|---|---|
| Windows | `%USERPROFILE%\Saved Games\Frontier Developments\Elite Dangerous` |
| macOS | `~/Library/Application Support/Frontier Developments/Elite Dangerous` |
| Linux (Steam) | `~/.steam/steam/steamapps/compatdata/359320/pfx/drive_c/users/steamuser/Saved Games/Frontier Developments/Elite Dangerous` |

You are looking for the folder containing files named `Journal.2026-05-19T003353.01.log`.

## 3 · Scan

Click **Scan my journals**. EDSG reads every journal file in the folder and
totals up only what this event's criteria ask for. A few years of logs takes
several seconds; the progress indicator shows how many events it has read.

When it finishes you see your results per criterion, with the measured units
and the points they earned, and your total.

If a criterion has a **cap**, you may see something like `1,500 t (of 1,963)` —
you mined more, but only the capped amount converts to points. That is the
organizer's rule, not a bug.

Your submission is saved automatically to `Documents/EDSG/Submissions`.

## 4 · Send it in

Click **Save submission** to put a copy wherever is convenient, then send that
file to your organizer however they asked.

The file is named for your Frontier ID, e.g. `F10467336.edsgs`. Do not rename
it — organizers rely on it to match submissions to commanders.

You can rescan and resend as often as you like before the deadline. Your newest
submission automatically supersedes any earlier one.

## What is in the file you are sending

This matters, so it is worth being specific. Your submission contains:

- your commander name and Frontier ID
- the total for each criterion in the event
- a breakdown by commodity, system or species where relevant
- up to twelve example events per criterion, with timestamps, as an audit trail
- scan diagnostics: how many files and events were read, the first and last
  timestamps, and the game versions found
- if the event is squadron-restricted, the squadron events proving you are a
  member

It does **not** contain your journals, your location history, your finances, or
anything about activity the event does not measure.

The file is readable JSON — open it in any text editor. Or run:

```bash
EDSG-Participant --cli inspect F10467336.edsgs
```

Bear in mind your organizer will see your commander name and Frontier ID. That
is unavoidable in a scored competition, but it is worth knowing.

## Getting your work counted early

If the event has capped criteria, they are filled **in the order the work
happened** — not the order submissions arrive. Refining the tonne that fills
a cap credits you, even if somebody else sends their file in first.

That also means work done after a cap is full earns nothing, so there is no
advantage in sitting on a submission, and none in rushing one either.

## Making it readable

**Options → Preferences** offers seven themes and per-colour overrides, so
you can match EDSG to the rest of your setup or pick something easier on the
eyes. The setting is shared with the organizer build if you run both.

The **Help** menu links to the documentation, the project on GitHub and a
place to report problems.

## Privacy and safety

EDSG reads only `Journal.*.log` files, on your machine. It does not modify the
game, inject code, read process memory, or contact Frontier's servers — or
anyone else's. Nothing is uploaded.

**Do not post journal files or `.edsgs` submissions publicly**, including in
bug reports. They identify you.

## Troubleshooting

**"This invitation could not be verified."** The file was modified in transit —
some chat clients mangle attachments. Ask for it again, ideally zipped.

**"No commander could be identified in that directory."** Wrong folder, or no
`Journal.*.log` files in it.

**"This folder holds journals for more than one commander."** Normal if you
have more than one Elite account on this machine — the game writes them all
to the same place. EDSG asks which one you are taking part as rather than
guessing, because your Frontier ID is what the submission is attributed to.

**"You are not eligible for this event."** The event is squadron-restricted and
your journals do not show current membership. The message says why. A common
cause is having joined but not logged in since; log into the game so a
`SquadronStartup` event is written, then rescan. A submission is still saved so
you can send it and let your organizer decide.

**Some journal lines could not be read.** Normal in small numbers — a line can
be truncated if the game exited mid-write. The count is reported to your
organizer for transparency. Large numbers suggest a damaged folder.

**A criterion scored zero that you expected to score.** Check the rule shown in
step 1: the period may exclude your activity, or a filter may be narrower than
you assumed. Ask your organizer — they can see the same rule.
