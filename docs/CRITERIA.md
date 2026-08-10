# Criteria reference

A criterion pairs a **metric** (what to count) with **filters** (which events
count) and a **scoring rule** (what those units are worth). Keeping the three
separate means a small set of metrics covers a very large space of events:
"tritium mined", "tritium sold to our carrier" and "anything sold at Jameson
Memorial" are the same two metrics with different filters.

This page is generated from the source, so it cannot drift from what the
application actually does.

## How filters combine

Within one field, values are **OR**-ed. Across fields, they are **AND**-ed.
So systems `Sol, Deciat` with commodities `Tritium` means *tritium, in Sol or
Deciat*. An empty field means no restriction.

Name matching is forgiving on purpose: it is case-insensitive, ignores
Frontier's `$name;` decoration, and matches on substrings. It also checks
**both** the internal name and the localised in-game name, so a filter written
as `lowtemperaturediamond` and one written as `Low Temp. Diamonds` behave
identically. Type whichever you have to hand.

## Measures


| Measure | Meaning |
|---|---|
| `count` | Number of events |
| `tonnage` | Tonnes |
| `credits` | Credits |
| `distinct` | Distinct items |

`distinct` is the one worth understanding. It counts each unique thing once
however often it recurs, so a body scanned three times contributes one unit.
For exploration criteria this is almost always what you want; `count` would
reward re-scanning the same body.

## Scoring

Each criterion has:

- **Points per unit** — may be fractional. For credit-based measures use
  something small, e.g. `0.000001` to make one point per million credits.
- **Cap** *(optional)* — the maximum units that convert to points. The raw
  total is still recorded and reported, so a capped result shows both figures.
- **Minimum** *(optional)* — a qualifying threshold. Below it the criterion
  scores nothing at all.

Caps are the main tool for keeping an event balanced: without one, a single
category with a high unit count can decide the whole standings.

## Metrics

### Raw journal events

`event_count`

Counts any journal event by name. Use this for anything the purpose-built metrics do not cover, including new event types.

- **Measures:** `count` (default `count`)
- **Journal events read:** whichever you name in the filter
- **Filters:** journal event names; systems, stations, station types

### Ore refined (mining)

`mining_refined`

Each MiningRefined event is one tonne delivered to the cargo hold by the refinery. Filter by commodity to score a single ore.

- **Measures:** `tonnage`, `distinct` (default `tonnage`)
- **Journal events read:** `MiningRefined`
- **Filters:** commodities; systems, stations, station types

### Commodities sold

`market_sell`

Commodity sales. Filter by commodity and by destination system, station, station type or market ID to target a specific buyer.

- **Measures:** `tonnage`, `credits`, `count` (default `tonnage`)
- **Journal events read:** `MarketSell`
- **Filters:** commodities; market IDs; systems, stations, station types

### Commodities bought

`market_buy`

Commodity purchases, filterable like sales.

- **Measures:** `tonnage`, `credits`, `count` (default `tonnage`)
- **Journal events read:** `MarketBuy`
- **Filters:** commodities; market IDs; systems, stations, station types

### Exobiology samples analysed

`exobio_scanned`

Completed biological samples. Only the third and final 'Analyse' scan of an organism counts, so partial samples do not inflate a score.

- **Measures:** `count`, `distinct` (default `count`)
- **Journal events read:** `ScanOrganic`
- **Filters:** genera, species; systems, stations, station types

### Exobiology data sold

`exobio_sold`

Biological data sold at Vista Genomics, by sample count or value.

- **Measures:** `count`, `credits` (default `count`)
- **Journal events read:** `SellOrganicData`
- **Filters:** genera, species; market IDs; systems, stations, station types

### Bodies scanned

`bodies_scanned`

Bodies scanned. Restrict to first discoveries to reward genuine exploration rather than re-scanning known space.

- **Measures:** `distinct`, `count` (default `distinct`)
- **Journal events read:** `Scan`
- **Filters:** first discoveries only; systems

### Bodies surface-mapped

`bodies_mapped`

Bodies mapped with surface probes. Restrict to first mappings to exclude already-mapped bodies.

- **Measures:** `distinct`, `count` (default `distinct`)
- **Journal events read:** `SAAScanComplete`
- **Filters:** first mappings only; systems

### Systems visited

`systems_visited`

Distinct star systems entered by hyperspace jump.

- **Measures:** `distinct`, `count` (default `distinct`)
- **Journal events read:** `CarrierJump`, `FSDJump`
- **Filters:** systems

### Exploration data sold

`exploration_sold`

Cartographic data sold, by system count or credit value.

- **Measures:** `credits`, `count`, `distinct` (default `credits`)
- **Journal events read:** `MultiSellExplorationData`, `SellExplorationData`
- **Filters:** market IDs; systems; systems, stations, station types

### Missions

`missions`

Missions by outcome. Filter by outcome, mission name, faction or destination.

- **Measures:** `count`, `credits` (default `count`)
- **Journal events read:** `MissionAbandoned`, `MissionAccepted`, `MissionCompleted`, `MissionFailed`
- **Filters:** factions; mission names, outcomes; systems, stations, station types

### Bounty vouchers

`bounties`

Bounty vouchers claimed, by count or credit value.

- **Measures:** `count`, `credits` (default `count`)
- **Journal events read:** `Bounty`
- **Filters:** factions; systems, stations, station types

### Combat bonds

`combat_bonds`

Combat bonds awarded, by count or credit value.

- **Measures:** `count`, `credits` (default `count`)
- **Journal events read:** `FactionKillBond`
- **Filters:** factions; systems, stations, station types

### Powerplay merits

`powerplay_merits`

Merits earned for a pledged power.

- **Measures:** `count` (default `count`)
- **Journal events read:** `PowerplayMerits`
- **Filters:** powers; systems, stations, station types

### Colonisation cargo delivered

`colonisation_contribution`

Commodities delivered to a colonisation construction site. Each delivery records exactly what the commander handed over, so this measures their own contribution rather than the site's total. Filter by commodity, or by market ID to target one build.

- **Measures:** `tonnage`, `count`, `distinct` (default `tonnage`)
- **Journal events read:** `ColonisationContribution`
- **Filters:** commodities; market IDs; systems, stations, station types

### Colonisation builds completed

`colonisation_completion`

Construction sites that reached completion and which the commander actually delivered to. Docking at somebody else's finished build does not count. Use it to reward seeing a construction through rather than dropping one load and leaving.

- **Measures:** `distinct` (default `distinct`)
- **Journal events read:** `ColonisationConstructionDepot`
- **Filters:** market IDs; systems, stations, station types

## Worked examples

**Mine 1,000 tonnes of tritium, capped**

> Metric `mining_refined`, measure `tonnage`, commodities `Tritium`,
> 1 point per unit, cap `1000`.

Each `MiningRefined` event is exactly one tonne leaving the refinery, so
tonnage is a straight count of those events.

**Sell painite to one specific fleet carrier**

> Metric `market_sell`, measure `tonnage`, commodities `Painite`,
> market IDs `3705689088`.

Market ID is the surest way to pin a carrier, because carrier names change and
callsigns repeat. Find it in the organizer's own journal after docking there,
or filter on station types `FleetCarrier` to accept any carrier.

**Reward genuine exploration, not tourism**

> Metric `bodies_scanned`, measure `distinct`, first discoveries only,
> 5 points per unit.

Without *first discoveries only*, re-scanning well-travelled systems scores as
well as going somewhere new.

**Completed massacre missions for one faction**

> Metric `missions`, measure `count`, mission name contains `massacre`,
> outcomes `completed`, factions `Nobles of Dagr`.

Mission names are matched against both the internal name
(`Mission_MassacreWing_name`) and the player-facing one, so `massacre` catches
the wing and solo variants together.

**Something EDSG has no metric for yet**

> Metric `event_count`, measure `count`, journal events
> `ColonisationContribution`.

The catch-all counts any journal event by name, including event types released
after this build of EDSG. It accepts the location filters too, so it can be
scoped to a system or station.

## A note on completeness

The purpose-built metrics cover mining, trade, exploration, exobiology,
combat, missions and Powerplay. Colonisation and Operations events do not yet
have dedicated metrics; score them with `event_count` in the meantime.

If you find yourself using `event_count` for the same thing repeatedly, that is
a good argument for a proper metric — see
[CONTRIBUTING.md](../CONTRIBUTING.md#adding-a-metric).
