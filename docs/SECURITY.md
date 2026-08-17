# Security model

This document says what EDSG's signatures do and do not prove. It is written
plainly because an organizer deciding whether to trust a set of results needs
the honest version, not a reassuring one.

## Summary

| Claim | Does EDSG prove it? |
|---|---|
| This invitation is the one the organizer issued | **Yes** |
| This invitation was not altered in transit | **Yes** |
| This submission is byte-for-byte what the participant's EDSG produced | **Yes** |
| This submission was generated from this specific invitation | **Yes** |
| This commander is currently in the organizer's squadron | **Yes**, from journal evidence |
| The participant's journal files were themselves unmodified | **No** |
| The participant actually did these things in-game | **No** |

The last two are the important ones, and they are unfixable by any tool of
this shape. Read on.

## What is signed, and how

EDSG signs with **Ed25519**. Keys are small, verification is fast, and the
primitive has no parameter choices to get wrong.

The signature covers the canonical encoding of a structure containing the
document payload, the document type, the signer's public key, and a timestamp.
Binding the type and key into the signed bytes matters:

- **Type binding** stops a valid invitation signature being lifted and
  replayed onto a submission, or the reverse.
- **Key binding** stops an attacker substituting their own public key and
  re-signing a modified payload while the file still claims to be the
  organizer's.

Both attacks are covered by tests in `tests/test_crypto.py`.

The encoding used for signing is deterministic and versioned as
`edsg-canonical-json-1`. Sorted keys, minimal separators, UTF-8, and NaN and
Infinity rejected outright since they are not valid JSON. Any change to this
encoding invalidates every signature ever produced, so the version travels
inside the envelope and a build that does not recognise it refuses to verify
rather than guessing.

## Keys and fingerprints

Each installation generates a signing identity on first run, stored in the
per-user configuration directory. **Each binary keeps its own**, under a
folder named for its role:

| Platform | Location |
|---|---|
| Windows | `%APPDATA%\EDSG\Organizer\` and `%APPDATA%\EDSG\Participant\` |
| macOS | `~/Library/Application Support/EDSG/Organizer/` and `.../Participant/` |
| Linux | `~/.config/EDSG/Organizer/` and `~/.config/EDSG/Participant/` |

Each role directory holds a `keys/` folder and a `settings.json`.

Separating them matters. An organizer's key is the one whose fingerprint
participants have been told to trust; a participant's is not. Keeping them
apart means copying a configuration between machines, or handing a laptop to
someone to take part on, cannot carry an organizer identity along with it.

Set `EDSG_CONFIG_DIR` to move the whole tree — useful for keeping an organizer
identity on removable media, or for testing. The role folders are created
inside whatever it points at.

**Private keys are stored unencrypted**, with owner-only permissions (`0600`)
on POSIX systems. This is a deliberate trade, and it is worth being clear what
is at stake: an attacker who reads an organizer's private key can forge
invitations that appear to come from them. They cannot touch that person's
Frontier account, their game, or anything else. Weighed against prompting for
a passphrase every time a file is signed, unencrypted storage is the
proportionate choice for a tool that runs community events. If your threat
model differs, keep the config directory on an encrypted volume.

### The fingerprint is the part that needs a human

A fingerprint is the first 128 bits of the SHA-256 of the public key, shown in
groups of four so two people can read it aloud without losing their place:

```
AF87 76A3 1301 ADED 2280 54DC 7394 5532
```

An invitation carries the organizer's public key inside it. That means EDSG can
verify the file is internally consistent and unmodified, but it **cannot**, on
its own, tell a participant that the key belongs to the person they think it
does — a forger can generate a key, sign their own invitation, and everything
will verify.

The fingerprint closes that gap, and it requires a human step:

1. The organizer publishes their fingerprint somewhere participants already
   trust — a pinned message in the squadron Discord, for instance.
2. Participants compare it against the fingerprint EDSG shows them when they
   open the invitation.

The participant application displays this prominently and tells the user to
check it. **This is the only defence against a forged invitation**, and it
works only if people actually do it.

## Submission verification

When an organizer closes an event, each `.edsgs` file is checked and rejected
with a specific reason if it fails:

- Signature does not verify — modified since it was generated.
- Wrong document type.
- Different event ID — submitted for another event.
- Different invitation fingerprint — generated from a different or forged
  invitation.
- Participant was not eligible, with the squadron reason attached.
- Superseded by a newer submission from the same commander.

Rejections appear in the standings report, so results are never quietly
smaller than expected.

## The limit: client-side trust

**EDSG cannot verify that a participant's journal files are genuine.**

Journals are plain text on the participant's own computer. A determined
participant can edit them before scanning, or write fabricated ones. The
resulting submission would be correctly signed, because it genuinely is what
their copy of EDSG produced from the files it was given.

This is not a flaw in the signing scheme. It is a property of any tool that
scores from client-side data, and no amount of cryptography fixes it. The only
real defences are Frontier's own server-side data, which is not available for
this purpose, or a live-witnessed event.

What EDSG does instead is **surface the evidence**, so an organizer can notice
when something looks wrong. Every standings report includes, per commander:

- total journal events parsed and files read
- the first and last event timestamps seen
- the game versions present in the journals
- counts of malformed or unreadable lines
- the signing key fingerprint
- a sample of matching events for each criterion, with timestamps

A commander whose journals show 400 events where everyone else shows 150,000,
or whose samples cluster implausibly, is visible in the report. A total that
looks impossible for the time available is visible in the report.

**Run events among people you have reason to trust.** EDSG makes cheating
detectable and inconvenient, not impossible.

## Privacy

EDSG makes **one** optional network connection, and only when an organizer
presses *Check names against Spansh* in the criterion editor. It sends the
system or station name typed into the filter field, and nothing else — no
commander name, no Frontier ID, no journal content, no identifier of any
kind. It is never called during scanning, scoring, signing or report
generation, and the participant build never calls it at all.

There is no telemetry, no update check and no account. Everything else EDSG
does works with the network unplugged.

A submission contains the commander name, Frontier ID, per-criterion totals, a
breakdown by commodity or system or species as relevant, up to twelve sample
events per criterion, scan diagnostics, and squadron evidence when the event
is squadron-restricted. It does **not** contain the journals.

Participants can inspect exactly what they are about to send — the file is
readable JSON, and `EDSG-Participant --cli inspect yourfile.edsgs` prints a
summary.

Organizers receive Frontier IDs, which are stable per-account identifiers.
Treat a folder of submissions as personal data: do not publish the raw files,
and prefer the Markdown or HTML report when sharing results publicly.

## Reporting a vulnerability

Please do not open a public issue for a security problem. Use GitHub's private
vulnerability reporting on the repository's Security tab.

Especially interested in: anything letting a signature verify against a payload
it does not cover, anything letting a forged invitation pass, anything letting
a submission be attributed to a commander who did not generate it, and any path
by which EDSG could write outside its intended directories.
