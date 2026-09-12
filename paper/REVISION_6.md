# Response to the sixth review

The most damaging point is correct and the error was ours.

## The confidence interval contradiction

The abstract reported 44.4 %, 95 % CI [42.3, 46.5]. That interval was computed
from a denominator of 2,151, which we obtained by dividing 955 by the reported
share. A later revision removed 2,151 from the text on the grounds that the run
had not recorded it — and left the interval standing.

The paper therefore did exactly what it warns against: reported a figure
derived by division as though it were measured. The interval is removed. The
abstract now gives the qualifying count alone. No interval can be reported
until a re-run logs the denominator, and `balanced_panel_check.py` is in the
repository for that purpose.

## Accepted and applied

**The bound is conditional on m, which we never measured.** Previously we wrote
"caps MobileRec at one aspect". That holds only at m = 1. The bound now reads
j ≤ 1.13m for MobileRec and 0.23m for Amazon, and the text states that m was
not estimated, that single numbers set m = 1 by convention, and that a reader
should carry the m.

**The threshold was never subjected to sensitivity analysis.** New Table 4
gives the bound at T = 5, 10, 15, 20, 30, 50. The conclusion is not
threshold-free: at T = 30 the MobileRec panel supports at most 1.13m aspects,
at T = 10 it supports 3.39m, so a ten-aspect taxonomy becomes arithmetically
possible once m ≥ 3. We say so rather than leaving it implicit, note why a low
threshold carries its own cost, and keep T = 30 because it was pre-specified.
Amazon fails at every threshold.

**The construct was misnamed.** No intervention dates, releases or firm
responses are observed. A "shock" is a fall in the measured series. New
Section 3.1 states that this is sentiment decline and return, not service
recovery in the sense of de Matos et al. (2007), and the title now reads
"Sentiment Decline and Return".

**The two findings were merged.** New Section 5.6 separates them: whole-review
category-level sentiment yields shock counts indistinguishable from noise; and
aspect-level series do not form at all. The second is logically prior and is
what the title concerns. The first establishes nothing about aspects.

**Scope was overstated.** New Section 4.1 states the subsamples plainly: 2.6 %
of MobileRec, one deliberately non-representative Amazon category. It also
notes why the density bound is the exception, being a rate rather than a count.

**"Agrees" was the wrong word** for the lexicon measure. It fails to reject, but
differs on outcome composition and censoring. Corrected.

**User-category cohorts may be feasible where user-item cohorts are not.** This
had not occurred to us and the reviewer is right. MobileRec's 5-core guarantees
five distinct apps per user, which may fall in one category, so a
category-level cohort could exist without any repeated app. We did not measure
the user-category or user-aspect repeat rate. The text now flags this as
unexamined rather than ruled out.

## Still outstanding

The three analyses in `code/followup_analyses.py` — Kaplan-Meier, PELT, 999
replicates — remain unrun. So does estimation of m, which now carries more
weight than before, since the bound is stated in terms of it. Human annotation
of a sample would give m directly and would also validate the lexicon; these
are the same task and would close two objections at once.
