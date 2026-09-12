# The follow-up run changed the paper

Three analyses were run. One of them contradicts what an earlier version of
this paper argued, and the manuscript now reports the contradiction rather than
resolving it.

## PELT is significant; the threshold rule is not

Same 27 category series, same block bootstrap null, 999 replicates.

| | Star: threshold | Star: PELT | Lexicon: threshold | Lexicon: PELT |
|---|---|---|---|---|
| Observed | 23 | 6 | 29 | 1 |
| Null mean | 28.39 | 1.77 | 26.19 | 0.80 |
| Ratio | 0.81 | **3.40** | 1.11 | 1.26 |
| Empirical p | 0.95 | **0.015** | 0.25 | 0.56 |

Earlier versions argued the PELT check was moot "once detection failed against
the null". That reasoning was wrong. The null comparison counts events; PELT
locates them; the questions are different and so are the answers.

Category-level star rating series contain temporal structure distinguishable
from the null. Our pre-specified event criterion does not capture it. Both
statements are now in the paper, in a new Section 5.6 and in the conclusion.

Three qualifications are stated alongside it: the lexicon does not reproduce
the result; six events across 27 series is few and the null mean below two
makes the normal approximation uncomfortable, hence the empirical p; and the
PELT penalty is a convention we adopted rather than tuned.

## The cohort claim was wrong at the level that matters

| Unit | Pairs | Repeats | Rate |
|---|---|---|---|
| User × item | 74,736 | 44 | 0.059 % |
| User × category | 73,563 | 1,205 | **1.638 %** |
| User × aspect | 14,244 | 198 | 1.390 % |
| User × category × aspect | 14,440 | 5 | 0.035 % |

Shocks are defined at category level, so the category rate is the relevant one.
It is 28 times the item rate. The paper had said the rates were "two orders of
magnitude below" what a cohort analysis needs; at category level the shortfall
is a factor of a few. The text now says a category-level cohort analysis is
marginal rather than impossible, and that a study with a larger panel should
attempt one rather than cite our item-level figure as grounds not to.

## The denominator, finally logged

2,150 category-months at 75 % presence. The figure we once recovered by
division was 2,151. One unit apart, which is exactly why a derived number
should not be reported as measured. The Wilson interval [42.3, 46.5] is
restored, now resting on a logged denominator.

Also logged: 2,291 at 50 % presence and 453 at 90 %.

## Kaplan-Meier, now reported

Median time to recovery is 3 months under star ratings and 15 under the
lexicon. A five-fold gap between two measures of the same episodes is not a
result about recovery; it is more evidence that the episodes are unstable. No
Cox model: 20 analysable episodes rule it out.

Block length sensitivity is reassuring: ratios of 0.78, 0.81, 0.85 at blocks of
3, 6 and 12 months.

## What remains

Only two protocol analyses are still unrun: a Cox model, which the episode
count forbids, and a transformer extractor, which would estimate m. The second
now matters more than before, since the density bound is stated in terms of m.

The annotation sheet is generated and unfilled. Filling it estimates m and
validates the lexicon in one pass.
