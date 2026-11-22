# 05 — Lifecycle

## 1. Status model

First pass: `Draft → Proposed → Active → (Amended)* → Expired | Terminated`.

Refined:

```
            (off-chain)
  draft ──propose──▶ proposed ──all required signers──▶ executed ──t ≥ start──▶ active
                        │                                                   │
                  t ≥ expires                                    t ≥ window end
                        ▼                                         ┌────────┴────────┐
                     lapsed                              ends_at set by Exit   natural end
                                                                 ▼                ▼
                                                            terminated         expired

  amendment: active ──propose(supersedes)──▶ active with a pending proposal
                    ──all required signers──▶ active under the new Agreement hash
```

**Status reported at time t.** Only `proposed` and `executed` are stored in State. The status reported at t is computed:

| Reported status | Condition |
|---|---|
| `proposed` | stored `proposed`, and no `expires`, or `t < expires` |
| `lapsed` | stored `proposed`, and `t ≥ expires` |
| `executed` | stored `executed`, and `t < start` |
| `active` | `Active(A, t)` |
| `terminated` | stored `executed`, `ends_at` is set, and `t ≥ ends_at` |
| `expired` | stored `executed`, `t ≥` window end, and not `terminated` |
| `suspended` | stored `executed`, inside its own window, but some parent is not Active |

Changes from the first pass, with reasons in DESIGN_NOTES:
- **Draft** is not a chain state. An unsigned Agreement is just data, and nothing about it needs consensus.
- **Executed** is added, because "everyone signed" and "in force" are different facts when the start date is in the future.
- **Amended** is not a status. An amendment is a transition from an Executed state to an Executed state under a new Agreement hash. The history is the chain.
- **Lapsed** and **suspended** are added so that every (chain, t) pair has exactly one reported status.

## 2. Transition rules

Each rule lists who must sign and what must be true. "Must sign" always means a signature that **speaks for** that Party: its own, or an agent's under a covering Mandate (A9). If any condition fails, `apply` returns ⊥ ([04-inference §1](04-inference.md#1-the-transition-function)). Nobody approves a transition.

### 2.1 `propose`, genesis

| | |
|---|---|
| Must sign | The author. The author must be a Party in `body.agreement`. |
| Preconditions | `S = ∅`. `Valid(body.agreement)` (A1, A6). If the Agreement has a Link clause, the parent chain is in the Bundle, is executed, and the Link's role binding holds ([04-inference §3.6](04-inference.md#36-link)). |
| Effect | `chain = hash(E)`, `status = proposed`, `agreement = hash(body.agreement)`, `pending = { event: hash(E), agreement, signed: [keys that signed E], expires }`. If `signed` already covers every required signer, execute immediately (§2.3 effect). |

### 2.2 `propose`, amendment

| | |
|---|---|
| Must sign | The author, who must be a Party of the current Agreement. |
| Preconditions | `S.status = executed`. `body.supersedes = S.agreement`. `Valid(body.agreement)`. Same Link checks as genesis. Any existing pending proposal is replaced. |
| Effect | Sets `pending` as in §2.1. The current Agreement stays in force until the amendment executes. Required signers are the Parties of both the current and the proposed Agreement (A2). |

Mutual termination is an amendment that sets the Window `end` to the agreed time.

### 2.3 `accept` of a proposal

| | |
|---|---|
| Must sign | The author, who must be a required signer of the pending proposal and not already in `pending.signed`. |
| Preconditions | `body.target = S.pending.event`. `E.at < pending.expires`, if set. |
| Effect | Add the author to `pending.signed`. When `pending.signed` covers every required signer: set `status = executed`, `agreement = pending.agreement`, `executed_at = E.at` (genesis only), and clear `pending`. Facts belonging to clauses removed by an amendment are dropped. Facts of clauses whose name and Term are unchanged carry over. |

### 2.4 `attest`

| | |
|---|---|
| Must sign | The author. |
| Preconditions | `S.status = executed`. The author holds some Role in the current Agreement. `body.claim.clause` names a clause of the current Agreement, and `body.claim.type` is a ClaimType that clause's Term declares, with data matching its schema. The clause's form accepts this author's role for this claim. |
| Effect | The clause form's effect ([04-inference §3](04-inference.md#3-clause-forms)). Every attestation is also recorded in that clause's facts, so later forms (Duty, Valuation, Exit) can read it. |

Attestations are allowed after the window ends, as long as the chain is executed. This lets final reports and payments for the last period be recorded after expiry or termination. Clause forms decide what such late claims mean.

### 2.5 `accept` of an attestation

| | |
|---|---|
| Must sign | The author, who must hold a Role that the target claim's clause lists in an `ack` field. |
| Preconditions | `body.target` is the hash of an earlier `attest` Event in this chain. The author has not already acknowledged it. |
| Effect | Records the acknowledgment and re-runs the clause form's effect for the target claim (e.g. a Selection becomes effective). |

## 3. Signature requirements at a glance

| Transition | Required signatures |
|---|---|
| Execute an Agreement | Every Party in `parties` (unanimity, A2) |
| Execute an amendment | Every Party of the old Agreement and of the new one |
| Attest a claim | The attesting Party, holding a Role the clause allows |
| Make a selection effective | Subject's attestation plus each `ack` role |
| Discharge a Duty | Obligor's attestation plus each `discharge.ack` role |
| Terminate unilaterally | A notice by an Exit `holders` role, with `requires` met |
| Expire | None. It follows from time. |
| Any of the above by an agent | The agent's signature plus a Mandate from the principal that covers the Event kind, the chain, and every parameter or claim value (A9). Otherwise the Event is rejected. |

## 4. Composition: participation

A member's participation in an aggregator–supplier Agreement is an ordinary Agreement with its own chain. It differs only in having a [UP:Participation](06-terms/UP-Participation.md) clause whose `parent` parameter is the ChainId of the master Agreement.

- The Link binds the master's aggregator and supplier as parties of the participation, so each of them signs every participation individually. The master needs no clause listing who may participate.
- `Active(P, t)` requires `Active(master, t)` (02, `Active`). If the master expires or terminates, every participation reports `suspended`, with no Event on the participation chain.
- One Party may hold the member role in any number of participation chains under any number of masters. Because every purchase or report is attested on exactly one chain (A9), two participations never compete for the same Event.
