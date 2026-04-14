# probid Philosophy

Minimal tool. Serious purpose.

probid helps people inspect Philippine public procurement quickly, critically, and with evidence.

## 1) Purpose

- Reduce harm: surface procurement red flags early.
- Increase public value: make scrutiny fast and repeatable.
- Increase understanding: explain findings clearly.

## 2) What probid is

- Local-first
- Explainable
- Practical
- Minimal by default

## 3) Non-negotiables

1. Evidence over opinion
- Every flag must show reason and supporting fields.
- Distinguish facts from interpretation.

2. Risk flags, not verdicts
- probid does not declare guilt.
- probid helps prioritize what deserves deeper review.

3. Simplicity first
- One obvious starting path.
- Good defaults.
- Advanced detail only on demand.

4. No dependency bloat
- Prefer free, local, reproducible workflows.
- Avoid paid/API-heavy architecture by default.

## 4) Legal baseline

- Primary baseline: RA 12009 + IRR.
- RA 9184-era logic is legacy context unless explicitly needed.

## 5) Detection stance

Prioritize high-signal, auditable heuristics:
- repeat/concentrated awards
- near-threshold and budget-use anomalies
- possible contract splitting patterns
- procurement mode outliers
- beneficial ownership transparency gaps (when available)

Each detection should include:
- trigger condition
- evidence used
- confidence
- likely false-positive risks

## 6) Product boundary

probid is not:
- a legal adjudication engine
- a replacement for COA/OMB/DOJ processes
- a heavy dashboard-first platform

## 7) Feature test

Ship only if all are true:
1. Improves detection signal or investigation speed
2. Keeps default workflow simple
3. Preserves explainability and traceability
4. Works without introducing paid dependencies

If any fail, do not ship.
