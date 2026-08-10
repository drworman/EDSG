# Colonisation and Operations

Notes on scoring Elite Dangerous' two newest squadron-relevant features,
based on journals from three commanders spanning March to August 3312, and on
Frontier's public information about the Operations update of 30 June 2026.

## Colonisation — fully supported

Colonisation produces two journal events, and they mean very different things.

### `ColonisationContribution` — the one that scores

Written when a commander hands cargo over at a construction site:

```json
{
  "timestamp": "2026-03-04T04:29:58Z",
  "event": "ColonisationContribution",
  "MarketID": 3955868162,
  "Contributions": [
    { "Name": "$CMMComposite_name;", "Name_Localised": "CMM Composite", "Amount": 18 },
    { "Name": "$Steel_name;", "Name_Localised": "Steel", "Amount": 1280 }
  ]
}
```

This is exactly what that commander delivered, so it is safe to score
directly. It becomes the `colonisation_contribution` metric.

The event carries no station name, only a `MarketID` — the same problem as
`MarketSell`. EDSG's existing market pre-pass resolves it, so a criterion can
be scoped to one construction site by name or by market ID. In the sample
journals every delivery resolved to a named site.

Measures: `tonnage` sums every commodity; `count` counts **deliveries**, not
line items, so one run carrying three commodities is one delivery; `distinct`
counts distinct commodities supplied.

### `ColonisationConstructionDepot` — a status snapshot, not a contribution

```json
{
  "event": "ColonisationConstructionDepot",
  "MarketID": 3955872514,
  "ConstructionProgress": 0.952471,
  "ConstructionComplete": false,
  "ResourcesRequired": [
    { "Name": "$cmmcomposite_name;", "RequiredAmount": 3912,
      "ProvidedAmount": 3912, "Payment": 6788 }
  ]
}
```

**`ProvidedAmount` is the site total from every commander**, not this one's
share, and the event fires whenever the site is viewed. In the sample, one
site produced 33 of these events, nine of them flagged complete.

Scoring it directly would be wrong twice over: it would credit one commander
with everyone else's cargo, and it would score repeatedly for re-docking.

So `colonisation_completion` uses it only to detect completion, and applies
two rules:

1. **Deduplicated by site.** Each construction site can score once, however
   many times its depot is viewed.
2. **Only for commanders who actually supplied it.** A completion counts only
   if the same journals contain a `ColonisationContribution` to that
   `MarketID`. Docking at somebody else's finished build scores nothing.

Supply made *before* the event window still qualifies a completion inside it —
the delivery proves the build is theirs, and the window governs when the
completion happened.

## Operations — not yet implemented, and the sample cannot tell us why

Operations launched on **30 June 2026** in game version 4.4.0.0: multi-stage
scenarios for a squad of up to four commanders, started from the mission
boards at starports, fleet carriers and squadron carriers. Six scenarios at
launch, in a default Mercenary Mode and a Powerplay Mode that awards merits.

### What the sample actually shows

The journals available during development span March 3312 (4.3.1.0, before
Operations existed) and July 3312 (4.4.0.2 and 4.4.0.3, after). They contain
**no Operations events of any kind**, and one related field:

```json
"Squadron": {
  "Squadron_Leaderboard_operationscore_highestcontribution": 0
}
```

Absent in March, present and `0` in July.

**The overwhelmingly likely explanation is simply that this commander did not
run any Operations.** The feature was about two weeks old at the time of the
last journal, and it is instanced squad content that needs three other
commanders or matchmaking. A commander who never entered an Operation writes
no Operations events and scores zero on the leaderboard.

### What this sample does *not* establish

It does not establish that Operations lacks journal events. Absence from one
commander's logs is not absence from the game, and drawing that conclusion
from this data would be unsound. Frontier has consistently added journal
events for new activities, and Operations is exactly the kind of feature that
would get them.

The public journal documentation mirrors were checked and are all stale — the
most recent covers Odyssey Update 14 from May 2023 — so the event names cannot
be confirmed from documentation either. This is an open question, not a
settled one.

### A likely shortcut worth testing

Operations are **started from the mission board**. If Frontier implemented
them on the existing mission framework, they may already write
`MissionAccepted` and `MissionCompleted` events, in which case EDSG can score
them *today* with no code change:

> Metric `missions`, measure `count`, outcomes `completed`,
> mission name contains `operation` — or whatever substring the mission
> names actually use.

Powerplay Mode awards merits, and `PowerplayMerits` is already a supported
metric, so merit-earning Operations activity is very likely covered already.

Both of these are hypotheses. Anyone with a journal from a completed Operation
can confirm or refute them in a minute by searching it for `Mission` and
`Operation`.

### On the leaderboard fields generally

Separately from Operations, the `Squadron_Leaderboard_*_highestcontribution`
fields in `Statistics` look tempting as a scoring source — they are exactly
the categories squadrons compete on — but they do not behave like a personal
counter.

The same commander delivered **13,117 tonnes** to construction sites on
2026-03-04 between 04:15 and 06:49. Three `Statistics` events bracket that
activity, at 04:11, 04:57 and 05:00, and
`Squadron_Leaderboard_colonisation_contribution_highestcontribution` reads
`443269` at all three. Four months later it still reads `443269`.

Several explanations fit: the field may hold the *squadron's* highest
contributor rather than this commander's total, it may be a seasonal figure
that only rolls over at season boundaries, or it may update on a server tick
rather than immediately. The sample cannot distinguish between them.

What follows either way is that these fields are not currently a safe basis
for ranking members of a squadron against each other. If the value is
squadron-wide, every member reports the same number and a delta-based metric
would score them identically — standings that look entirely plausible and mean
nothing. That is worse than having no metric.

If the semantics are pinned down later, a delta metric is straightforward:
take the value from the last `Statistics` at or before the window start and
subtract it from the last one at or before the window end. Roughly thirty
lines, following the pattern in `core/metrics.py`.

### What would settle all of this

A journal from a commander who has **completed an Operation**. That single
file would show the event names, whether missions events are reused, and
whether `operationscore` moves. For the leaderboard question specifically,
journals from **two commanders in the same squadron over the same period**
would show immediately whether `highestcontribution` is personal or shared.

Until then, `event_count` scores any Operations event by name the moment
someone identifies it, with no new EDSG release required.

## Coverage summary

| Feature | Journal evidence | Status |
|---|---|---|
| Colonisation deliveries | `ColonisationContribution`, 12 events, 13,117 t | Supported |
| Colonisation completion | `ColonisationConstructionDepot`, 41 events, 2 sites | Supported |
| Colonisation system claims | none in sample | `event_count` |
| Operations | none in sample; commander ran no Operations | Not implemented. Possibly already covered by `missions` and `powerplay_merits`; `event_count` covers any event by name |
