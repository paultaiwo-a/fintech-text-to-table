# Scoring

Weights live in `config/scoring.yaml`. Bump `extractor_version` when they change.

## Sentiment (-1 to 1)

```text
pos / neg = lexicon hits (negation within 3 tokens flips the hit)
sentiment_score = (pos - neg) / (pos + neg + 1)
label: <= -0.2 negative, >= 0.2 positive, else neutral
```

## Frustration (0 to 1)

```text
0.4 * (phrase hits / 3, capped)
+ 0.3 * repeated-contact flag
+ 0.2 * exclamation or ALL-CAPS flag
+ 0.1 * (sentiment <= -0.5)
```

## Severity (0–100)

| Component | Points |
| --- | --- |
| Amount none / &lt;$100 / $100–999 / $1k–9,999 / ≥$10k | 0 / 5 / 15 / 25 / 30 |
| Delay none / &lt;7d / 7–29 / ≥30 | 0 / 5 / 15 / 25 |
| Escalation | 20 |
| Switching intent | 15 |
| Sentiment ≤ -0.5 | 10 |

Bands: low 0–24, medium 25–49, high 50–74, critical 75–100.

## Lead signal (0–100)

| Component | Points |
| --- | --- |
| Switching intent | 40 |
| Challenger-addressable pain point | 25 |
| Amount ≥ $1,000 | 15 |
| Competitor mentioned | 10 |
| In last 90 days of data | 10 |
