# Goal tiers and rewards

Every event runs as a community goal in Frontier's shape: a collective
target the whole squadron pushes toward, with rewards for the commanders
who did the pushing. Rewards themselves are optional — leave them off for
a plain leaderboard.

The shape follows Frontier's own community goals, because that is the format
squadrons already know how to read. Two things are happening at once, and
they are easy to confuse:

| | Measures | Looks like |
|---|---|---|
| **Goal tiers** | The **collective** total, everyone's points added together | `Tier 3/5` |
| **Reward bands** | **Individual** rank against everyone else | `Top 10 CMDRs`, `Top 25%` |

The two combine. The band a commander lands in decides *which* payout they
get; the goal tier the squadron reached decides *how much that payout is
worth*.

Turn it on in the organizer under **2 · Criteria → Goal tiers & rewards**.
Leave it off and reports look exactly as they did before.

## Goal tiers

**You never type a target.** The top tier in use is worth exactly what your
criteria are worth: every criterion's unit cap multiplied by its points per
unit, added together. That number cannot drift out of step with the criteria,
because it *is* the criteria.

The tiers below it step down in equal shares. Untick the ones you do not want
— for a four-tier event, untick Tier 5 — and the rest rebalance themselves:

| Tiers in use | Step | Thresholds, on a 16,000-point event |
|---|---|---|
| 5 | 20% | 3,200 · 6,400 · 9,600 · 12,800 · 16,000 |
| 4 | 25% | 4,000 · 8,000 · 12,000 · 16,000 |
| 3 | 33% | 5,333 · 10,667 · 16,000 |

Tiers are listed **highest first**, in the organizer and in the reports: a
squadron climbs toward the top tier, so reading downward reads back down the
ladder. **Five is the maximum**, matching Frontier.

**Tier 1 is the floor.** If the squadron does not reach it, no rewards are
paid at all — the event did not achieve what it set out to.

## The unit cap, and why it matters more than it looks

Every criterion needs a **Unit Cap**. It is not just a limit on runaway
scoring; it is what the criterion races for.

A capped criterion is filled **in the order the work happened**, across
everybody. If a criterion is capped at 100 tonnes of tritium, the hundredth
tonne refined ends it — regardless of whose submission arrived first:

| Time | Commander | Refined | Cap filled | Credited |
|---|---|---:|---:|---:|
| 10:00 | A | 43 | 43 | 43 |
| 11:00 | B | 60 | 100 | 57 |
| 12:00 | A | 70 | 100 | 0 |

CMDR A refined more over the window and submitted first, and is still
credited 43, because CMDR B did the work that filled the cap.

This is why submissions carry the timestamp of each scoring event, and why
the cap is required: it bounds how much of a journal has to travel. A
commander only ever needs to send their earliest events covering the cap,
because nothing past that could score even if they led the whole way.

### Minimum per CMDR

A separate, optional participation floor. A commander credited fewer units
than the minimum scores nothing for that criterion, which keeps a token
contribution out of the rewards. Their units are not redistributed — that
would change who filled the cap and when.

## Rewards

Set one number: **Maximum Reward Pool in Credits**. That is the most you will
pay out in total, across everyone, and it is only reached if every goal tier
is reached.

The pool unlocks a share per tier. On a five-tier event with a 1,000,000,000
pool:

| Reached | Unlocked |
|---|---|
| Below Tier 1 | nothing |
| Tier 1 | 200,000,000 |
| Tier 4 | 800,000,000 |
| Tier 5 | 1,000,000,000 |

There is no escalation to configure. The growth *is* the escalation.

### How the pool is shared out

Two settings, defaulting to 10 and 25%:

| Setting | Means |
|---|---|
| **Bonus goes to the top** | How many leading commanders share a bonus. Set to 0 for a purely proportional split. |
| **Bonus share of the pool** | How much of the pool that bonus takes. |

The unlocked pool splits in two, and **both halves are proportional to what
each commander contributed**:

- The bonus is shared *within* the top group, by contribution.
- The remainder is shared among *everyone*, by contribution.

So a commander who contributed 9.29% of the goal receives 9.29% of the
remainder, plus their proportional slice of the bonus if they placed inside
the top group.

### Why the bonus is proportional too

A flat per-head bonus — everyone in the top ten gets the same 2.5% — is
simpler to describe and badly wrong in practice. In a field of one commander
who did 99% of the work and twenty-five who did 0.04% each, nine of the
minnows land in the top ten by tie-break and collect the same flat share as
the whale, while the tenth minnow, who did identical work, collects
one eighty-fifth of it.

Making the bonus proportional inside the group removes that entirely.
Commanders who contributed nothing receive nothing.

### The step at the edge of the bonus

The last commander inside the top group earns roughly twice the first one
outside it. That is inherent to having a leaderboard bonus at all, and it is
deliberate: if you want the larger payout, place higher. Set **Bonus goes to
the top** to 0 to remove it and pay purely by contribution.

### Ties

Commanders on equal points share a rank — 1, 2, 2, 4 — and are **paid
identically**. If a tie straddles the edge of the top group, the whole tie is
brought in, which dilutes the bonus for everyone in that group. The
alternative would be deciding real money on which file happened to be read
first.

## The distribution matrix

Closing a tiered event publishes a table of every commander: their rank,
points, share of the goal, the bonus and proportional halves separately, and
the exact figure they are owed. It is ordered so an organizer can work down
it one payment at a time, and a star marks the commanders in the top group.

## What the reports show

Every format carries the board:

- **HTML** — the tier readout, a meter with each threshold marked and reached
  tiers picked out, how far the next tier is, a summary of how the pool
  splits, and the full distribution matrix. Entirely self-contained: the
  stylesheet is inline and the squadron logo is embedded, so the file can be
  mailed or uploaded without carrying anything alongside it.
- **PDF** — the same, drawn to print cleanly in black and white, and
  paginated by subject: the event summary and criteria on page 1, goal
  progress on page 2, rewards on page 3, then the standings.
- **Markdown** — a text meter that pastes into Discord, with a
  who-receives-what table.
- **JSON** — the whole structure under a `progress` key, for a bot or site.

The reward table shows, per band, how many commanders fell into it, the
points range it covers, and what each of them is owed.

## EDSG does not pay anyone

It works out and publishes who is owed what. Handing over the credits happens
in game, by the organizer, exactly as it would without EDSG. Treat the reward
figures as a statement of intent to your squadron, not a transaction.
