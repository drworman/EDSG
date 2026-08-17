# Goal tiers and rewards

An event can be a plain leaderboard, or it can carry a **goal**: a
collective target the whole squadron pushes toward, with rewards for the
commanders who did the pushing.

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

Set a **target** — the total points from everyone combined that completes the
goal — then define up to five tiers on the way there.

You can type the thresholds, or let EDSG work them out:

| Button | Does |
|---|---|
| **Even split of target** | Divides the target into equal steps. Any remainder goes into the first tier, so the later thresholds stay round and the last lands exactly on the target. |
| **20% steps down from target** | Works downward from the target: 100%, 80%, 60%, 40%, 20%. |
| **20% steps up from Tier 1** | Works upward from whatever Tier 1 is set to. Use this when you know what a realistic first tier looks like but not where the ceiling is. |

Thresholds must increase, and the last cannot exceed the target. EDSG refuses
to issue an invitation otherwise, since neither mistake can be corrected once
the invitation is signed.

**Five is the maximum**, matching Frontier. More tiers than that stop being
readable on a progress board.

## Reward bands

Bands rank the commanders who contributed. Each band selects its members one
of two ways:

- **Top N commanders** — a fixed count, like Frontier's `Top 10 CMDRs`.
- **Top X% of field** — a share of everyone who took part.

Bands fill **from the top down, and each commander is paid by the best band
they reach**. So a `Top 10 CMDRs` band sits *above* `Top 25%` rather than
inside it, and nobody is paid twice. This is how Frontier's own tables read:
their `Top 10 CMDRs` row shows a higher contribution range than the `Top 25%`
row beneath it.

The default layout is Frontier's, and **Reset to Frontier's layout** puts it
back:

```
Top 10 CMDRs    top 10 commanders
Top 25%         top 25% of field
Top 50%         top 50% of field
Top 75%         top 75% of field
Top 100%        everyone who took part
```

With a small field the lower bands may come out empty. They are still shown
on the board, so participants can see what a bigger turnout would have paid.

## Escalation

Every band's reward is multiplied by the escalation figure for the tier the
goal reached. Leave them all at 1 for flat rewards.

| At tier | 1 | 2 | 3 | 4 | 5 |
|---|---|---|---|---|---|
| Multiplier | ×1 | ×1.5 | ×2 | ×3 | ×4.5 |

A `Top 10 CMDRs` band paying 50,000,000 pays 100,000,000 if the squadron
reaches Tier 3.

This is why the configuration is ten inputs rather than twenty-five: a base
payout per band and a multiplier per tier describe the same matrix Frontier
publishes, without asking you to fill in every cell.

## What the reports show

Every format carries the board:

- **HTML** — the tier readout, a meter with each threshold marked and reached
  tiers picked out, how far the next tier is, and the reward table.
- **PDF** — the same, drawn to print cleanly in black and white.
- **Markdown** — a text meter that pastes into Discord.
- **JSON** — the whole structure under a `progress` key, for a bot or site.

The reward table shows, per band, how many commanders fell into it, the
points range it covers, and what each of them is owed.

## EDSG does not pay anyone

It works out and publishes who is owed what. Handing over the credits happens
in game, by the organizer, exactly as it would without EDSG. Treat the reward
figures as a statement of intent to your squadron, not a transaction.
