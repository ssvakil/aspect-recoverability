# Response to the ninth review

All seven defects confirmed and corrected. The most serious was ours and the
review was right that it was the same failure mode we had criticised in an
earlier draft.

## 1. Seven stale figures from the old denominator

R was corrected to 34.8 in one section and left at 33.9 everywhere else. The
consequences propagated: 1.13m became 1.16m, 3.39m became 3.48m, 16.9 became
17.4, m >= 8.9 became 8.6, m >= 2.7 became 2.6. Seven locations, including the
abstract and conclusion.

The review notes this is the same error we congratulated ourselves for catching
at 2,150 versus 2,151, only three percent rather than one unit and repeated
seven times. That is fair.

## 2. Section 5.13 contradicted itself

Paragraph one withdrew the inference that measure divergence indicated noise.
Paragraph three restated it verbatim: "should not diverge this way if the
episodes being classified were real events". An editing remnant. The paragraph
is removed and replaced with a sentence explaining why the figure is shown at
all.

## 3. p-value provenance was stale

The text still justified a normal approximation by "the small replicate count"
after moving to 999 replicates. All p-values are now stated as empirical
quantiles under the (b+1)/(B+1) convention, with the superseded normal
approximations named so a reader comparing versions is not confused.

## 4. The positive control was missing from the controls table

It is now the seventh row, with its failure mode ("a detector may fail silently
on shocks that are present") and bias direction ("would let a null result be
read as evidence of absence"). The count above the table is corrected from six
to seven.

## 5. The synthetic configuration was asserted as "matched"

It was not matched; it was chosen. The text now says so: 40 months is the modal
run length but not the range, which is 9 to 43; phi = 0.6 was selected rather
than estimated. Power against phi is reported, falling from 0.89 at phi = 0 to
0.59 at phi = 0.85, so our figure sits mid-range rather than at the favourable
end. The false positive rate is the one quantity checkable against the data,
and its agreement with the observed null is what supports the synthetic series
being representative.

## 6. Section 3.7 contradicted Section 5.6

"77 tests covering shock detection" against "none measures whether the
criterion recovers a shock that is present". The first now reads "shock
classification", and the text states explicitly that classification correctness
and detection power are separate properties.

## 7. Conclusion omitted the Bonferroni correction

Present in the abstract, absent in the conclusion. Now carries both values.

## Also corrected

The abstract claimed "no absence of structure", a double negative that asserts
something the positive control forbids. It now says neither presence nor
absence, because the criterion cannot distinguish them.

The power table caption now gives the trial count, 27 per cell, and the
standard error, roughly 0.09, and states that the non-monotonicity at 0.5 SD
should be read as noise.

The corpus-availability claim generalised from two corpora. It now says we
surveyed no others and names Yelp, Goodreads, Steam and TripAdvisor as
candidates for a review we did not perform.

## On the bound

The review objects that "we would have saved several weeks by computing it
first" inflates an elementary inequality. The sentence is removed. The text now
states the position we described in correspondence: nothing is claimed for the
inequality, only that computing it before assembling a panel is not standard
practice.

## Verification after correction

    stale figures (1.13m, 3.39m, 8.9, 16.9)   0
    self-contradicting paragraph               0
    stale p-value justification                0
    "saved several weeks"                      0
    Bonferroni in conclusion                   present
    positive control in controls table         present
    dangling cross-references                  0
    "??" in rendered PDF                       0
    references cited / defined                 52 / 52
