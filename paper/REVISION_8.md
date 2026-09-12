# Response to the eighth review

Every numeric criticism was correct. Two of them were errors of ours that no
previous review caught.

## The positive control, and what it found

The review said a negative study that never validates its instrument cannot
claim absence, only failure to find. That is right, and we ran the control.

Shocks of known magnitude were injected into AR(1) series matched to the
observed panel. Results:

| Injected | 2 mo | 3 mo | 6 mo |
|---|---|---|---|
| 0.5 SD | 0.56 | 0.44 | 0.56 |
| 1.0 SD | 0.56 | 0.48 | 0.67 |
| 2.0 SD | 0.63 | 0.67 | 0.74 |
| 3.0 SD | 0.70 | 0.78 | 0.89 |

**False positive rate: 1.00.** Every clean series with nothing injected
produces at least one detection.

This is not a late discovery so much as the quantitative form of what the
bootstrap null already said: 28.39 detections across 27 series is 1.05 per
series, and the synthetic control gives 1.00. The agreement also confirms the
synthetic series resemble the real ones.

The consequence is stated in the paper: we cannot claim a shock would have been
found had one existed, since the criterion recovers about two-thirds of
realistic ones. And the observed 0.85 detections per series is *below* what the
criterion produces on noise. A rule with a unit false positive rate can only
report that the data are not noisier than noise.

## PELT does not survive correction

Four tests, two procedures by two measures, one dataset, one null. Bonferroni
takes p = 0.015 to p = 0.060. The paper now reports both values and draws no
conclusion from either.

An earlier version said correction "would only strengthen the reported
conclusion". That was true while every test was null and false the moment one
was not. The sentence is removed.

## R was computed on the wrong denominator

R = 74,780 / 2,208 = 33.9 used the theoretical maximum. The logged denominator
is 2,150, giving R = 34.8. The bound table is recomputed: 1.16m at T = 30
rather than 1.13m, 3.48m at T = 10 rather than 3.39m. The direction is
unchanged; the figures were wrong.

## Stale numbers from the 30-replicate run

The abstract carried 999-replicate figures while Section 5.5, Table 5 and
Section 3.4 still carried 30-replicate ones. All now report the 999-replicate
run: 28.39 ± 3.77, ratio 0.81, empirical p = 0.95, with the ratio interval
[0.64, 1.15].

## "Marginal" overstated the cohort position

23 episodes at 1.64 % gives 0.38 expected returning reviewers across the whole
study. A tenfold panel gives four. The text now says out of reach at this
scale by a wide margin, while noting the margin is tens rather than the
hundreds the item-level rate implied.

## The lexicon divergence argument was a logical error

We had offered the star/lexicon divergence as evidence the episodes were not
real. A mean star rating and a lexicon score are not two measurements of one
construct, so divergence is expected rather than diagnostic. The inference is
withdrawn. The comparison is kept only to note that every conclusion can be
read from the star-rating column alone.

## Where we disagree

The review calls the density bound a trivial identity dressed as a
contribution. It is an identity, and the paper says so. Our claim for it is
narrow: not that the inequality is deep, but that computing it before
collecting data is not standard practice, and that stating it in a form that
transfers has some value. The sentence about saving weeks is our own admission
of the same point, not rhetoric meant to inflate it. A reader who finds the
bound obvious has understood it correctly.

The review also asks that we find a published study whose numbers violate the
bound. We searched and found none, which is reported. We will not manufacture
a target.
