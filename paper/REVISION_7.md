# Response to the seventh review

## Three real defects, corrected

**Table 6 miscounted its own rows.** The text read "Five were implemented and
exercised" above a table listing six: right-censoring, block bootstrap null,
cohort versus population, gap-aware segmentation, balanced panel, guarded ratio
reporting. Corrected to six implemented and one specified-but-unexercised.

**The nine-month figure looked like arithmetic error.** Baseline is six months
and the shock requirement two, so a reader reaches eight and finds nine in the
text. The implementation admits runs *exceeding* the combined requirement, and
eight months would leave no month in which recovery could be observed. The
reasoning is now stated rather than left to be reconstructed.

**Shares quoted without their denominators.** The confidence interval was
removed in the previous round but the 44.4 % share still appeared in four
places with no note attached. Each now carries a dagger to a table footnote
stating that the denominator was not logged, that no interval is attached, and
that an earlier draft wrongly attached one.

## Two findings now kept apart in the abstract and conclusion

The reviewer is right that Section 5.6 separated them while the abstract and
conclusion still ran them together. Both now state the levels explicitly: at
category level, whole-review sentiment yields shock counts indistinguishable
from noise, which concerns whole-review sentiment and establishes nothing about
aspects; at aspect level the question does not arise, because the series do not
form. The conclusion also foregrounds the power limit: this is a failure to
detect, and a signal below a third above chance remains possible.

## Three reported typos do not exist

"Mohawehs", "Tsoros", "Kezough". Checked in the rendered PDF:

    Mohawehs False    Mohawesh True
    Tsoros   False    Tsiros   True
    Kezough  False    Kezouh   True

This is the fifth consecutive review to report these three spellings. They have
been correct in every version. Anything reported as an editorial defect should
be checked against the PDF before it is "fixed", or a clean file will acquire
real errors.

The reported garbled Table 3 row, "485,1342,28644.5%", is column content run
together by text extraction. The typeset table is correct.

## Unchanged and unresolved

The review restates the substantive gaps from the previous round, and they
remain open because they need runs rather than edits:

1. **m is not measured.** The bound is linear in m and every single-number
   statement sets m = 1. Human annotation of a sample gives m directly and
   validates the lexicon at the same time. This is now the single highest-value
   outstanding task, since the bound is stated in terms of m.
2. **The denominator is not logged.** One re-run of `balanced_panel_check.py`
   with denominator logging closes it.
3. **Kaplan-Meier, PELT, 999 replicates.** Implemented in
   `code/followup_analyses.py`, 22 self-tests passing, not yet run.
4. **User-category and user-aspect repeat rates.** Not measured. The 5-core
   filter makes a category-level cohort possible in principle.

Items 2 to 4 are minutes of compute. Item 1 is a day of annotation. Until they
are done, the reviewer's assessment of the manuscript's readiness is correct
and we do not dispute it.
