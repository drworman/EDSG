# File formats

EDSG uses three file types. All are UTF-8 JSON, readable in any text editor,
and stable within a schema version.

| Extension | Name | Signed | Flows |
|---|---|---|---|
| `.edsgi` | Invitation | yes | organizer → participants |
| `.edsgs` | Submission | yes | participant → organizer |
| `.edsgevent` | Event draft | no | organizer's own working copy |

## The signed envelope

Both signed types share an envelope:

```json
{
  "edsg": {
    "algorithm": "ed25519",
    "signature": "base64…",
    "signer_label": "EDSG event organizer"
  },
  "canonical_form": "edsg-canonical-json-1",
  "doc_type": "edsg.invitation",
  "payload": { },
  "public_key": "base64…",
  "signed_at": "2026-08-09T21:14:03+00:00"
}
```

The signature covers the canonical encoding of everything except the `edsg`
block — that is, the payload together with `canonical_form`, `doc_type`,
`public_key` and `signed_at`. Including the document type and the key in the
signed bytes prevents a signature being transplanted between document types or
re-attributed to a substituted key.

`canonical_form` identifies the encoding used to produce the signed bytes:
sorted keys, `,`/`:` separators, UTF-8, no escaping of non-ASCII, and NaN and
Infinity rejected. A build that does not recognise the value refuses to verify
rather than guessing, so a future encoding change cannot silently invalidate
old files.

## Invitation payload

```json
{
  "schema_version": 1,
  "event_id": "7812f0fe19a04097a4d7a92cd3ea695e",
  "name": "Mining & Logistics Summer Push",
  "description": "Squadron-only mining and exploration drive.",
  "organizer_name": "CMDR HUGH JASSOLE",
  "window": { "start": "2026-05-01T00:00:00+00:00",
              "end":   "2026-09-01T00:00:00+00:00" },
  "eligibility": "squadron",
  "squadron": { "squadron_id": 110393, "name": "MINING AND LOGISTICS LTD" },
  "tie_break": "earliest_submission",
  "state": "open",
  "criteria": [ ]
}
```

`window` bounds may be `null` for an open-ended event. `squadron` is `null` when
`eligibility` is `open`.

### A criterion

```json
{
  "criterion_id": "a1b2c3d4e5f6",
  "label": "Tritium refined",
  "kind": "mining_refined",
  "measure": "tonnage",
  "points_per_unit": 2.0,
  "unit_cap": 1500,
  "minimum_units": null,
  "notes": "",
  "filters": {
    "commodities": ["Tritium"],
    "systems": [], "stations": [], "station_types": [], "market_ids": [],
    "event_names": [], "mission_names": [], "mission_outcomes": [],
    "factions": [], "genera": [], "species": [], "powers": [],
    "first_discovery_only": false, "first_mapped_only": false
  }
}
```

`criterion_id` is the join key between an invitation and the per-criterion
results in a submission. It is stable across edits to a criterion, so results
stay attributable.

See [CRITERIA.md](CRITERIA.md) for every valid `kind` and `measure`.

## Submission payload

```json
{
  "schema_version": 1,
  "event_id": "7812f0fe19a04097a4d7a92cd3ea695e",
  "event_name": "Mining & Logistics Summer Push",
  "invitation_fingerprint": "AF87 76A3 1301 ADED 2280 54DC 7394 5532",
  "commander_name": "HUGH JASSOLE",
  "commander_fid": "F10467336",
  "total_points": 18325.1,
  "eligible": true,
  "eligibility_reason": "Membership confirmed by SquadronStartup event with no later departure.",
  "generated_at": "2026-08-09T21:20:11+00:00",
  "generator_version": "20260810",
  "results": [ ],
  "squadron_evidence": { },
  "scan": {
    "files_read": 154,
    "entries_parsed": 157131,
    "malformed_lines": 0,
    "unreadable_files": [],
    "first_event": "2026-05-19T05:33:47+00:00",
    "last_event": "2026-08-08T03:41:22+00:00",
    "game_versions": ["4.3.3.0", "4.4.0.3"]
  }
}
```

`invitation_fingerprint` binds the submission to the invitation it came from, so
an organizer can reject results built against a different or forged one.

`scan` is the audit trail. It is what lets an organizer notice an implausible
submission — see [SECURITY.md](SECURITY.md).

### A result

```json
{
  "criterion_id": "a1b2c3d4e5f6",
  "label": "Tritium refined",
  "raw_units": 1963.0,
  "counted_units": 1500.0,
  "points": 3000.0,
  "samples": ["2026-05-19T20:45:00+00:00 refined 1 t Tritium in Nessa"],
  "detail": {
    "kind": "mining_refined",
    "measure": "tonnage",
    "events_matched": 1963,
    "breakdown": { "Tritium": 1963.0 },
    "breakdown_truncated": false
  }
}
```

`raw_units` is what the participant actually achieved; `counted_units` is what
scored after any cap or minimum. Both are kept so a capped result is legible
rather than looking like an error.

`breakdown` holds at most 40 keys, `samples` at most 12 entries;
`breakdown_truncated` says whether anything was dropped.

## Filenames

Submissions are named for the Frontier ID: `F10467336.edsgs`. Frontier IDs are
stable and unique per account, whereas commander names are neither. Do not
rename them.

Invitations default to a slug of the event name but may be renamed freely — the
event identity lives in `event_id`, not the filename.

## Compatibility

`schema_version` covers document structure. A file with a higher version than
the reading build is refused with a message telling the user to update, rather
than being partially parsed.

An unknown metric `kind` is likewise refused rather than scored as zero. A
participant on an older build who receives an invitation using a newer metric
is told to update — quietly scoring zero would look like poor performance
rather than a version mismatch.

## Working with them programmatically

The JSON report from a closed event is the intended integration point: it
carries the event definition, every accepted submission's per-criterion detail,
and the rejection list.

```bash
EDSG-Organizer --cli inspect invitation.edsgi
EDSG-Organizer --cli inspect F10467336.edsgs
EDSG-Organizer --cli close event.json --submissions ./subs --out ./reports
```

`inspect` verifies the signature before printing anything, so it doubles as a
validity check.
