# penKeep

penKeep records why an investor owns a position, checks new evidence against that written case, and preserves the decisions made afterwards.

## Language

**Written case**:
The investor's recorded reason for owning a position and the evidence that would change their mind.
_Avoid_: AI thesis, generated thesis

**Decision state**:
The current relationship between a position's written case and relevant evidence: Calm, Changed, Needs a decision, or Needs a written case.
_Avoid_: Health score, pulse score, thesis quality

**Case quality**:
How specific, monitorable, and current a written case is, independent of whether new evidence has changed it.
_Avoid_: Decision state, stock quality

**Review overdue**:
A case-quality condition indicating that the written case has not been revisited within its review policy.
_Avoid_: Changed, broken

## Relationships

- A position has at most one active **Written case**.
- A **Written case** has one **Decision state** and one **Case quality**.
- New relevant evidence may move the **Decision state** from Calm to Changed or Needs a decision.
- **Review overdue** affects **Case quality** but does not imply that evidence changed.

## Example dialogue

> **Dev:** "This case is overdue. Should its Decision state become Changed?"
> **Domain expert:** "No. Keep the Decision state Calm unless evidence changed; show Review overdue as Case quality."

## Flagged ambiguities

- "Thesis health" previously mixed evidence state with writing quality. These are now **Decision state** and **Case quality** respectively.
