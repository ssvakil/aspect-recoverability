# Response to the second review round

Two reviews received. Verified each claim before acting; several were correct
and material, two were misreadings.

## Corrected

**Title narrowed.** "from Public Review Corpora" asserted a general negative
from two datasets. Now "from Two Large Public Review Corpora".

**The density bound was only computed for MobileRec.** Both reviews asked why.
It is now computed for Amazon as well, and Amazon fails it harder: 82,041
reviews over 11,925 product-months gives R = 6.9 reviews per product-month
against a threshold of 30, short by a factor of 4.4 before any aspect split.
This is stated as the reason no aspect analysis was attempted there.

**The bound assumed even distribution.** One review noted real extractors are
skewed. The bound is now stated generally as j ≤ Rm/T and does not require
uniformity: skew can lift one aspect above threshold but cannot raise the
total, so the cap on how many aspects qualify holds under any assignment.

**The transformer objection is now answered rather than avoided.** A better
extractor raises m, and the bound is linear in m. Ten qualifying aspects on the
MobileRec panel would need m ≥ 8.9 — nine attribute judgements per app review.
Three would need m ≥ 2.7. We state plainly that no transformer baseline was
run and that a reader who believes m ≥ 3 is attainable should treat this part
as untested.

**27 series versus 16 categories.** Not a contradiction but never explained.
Detection runs on any contiguous run over nine months; a full
shock-and-recovery window needs 26. Sixteen categories have the latter, and 27
runs exceed the former across 46 categories because sparse months split
categories into several runs. Series between nine and 25 months can host a
shock whose outcome is then necessarily censored, which accounts for part of
the censoring rate.

**44.4 % versus 44.5 %.** Both correct, different quantities: 955/2,151
windowed balanced against 2,286/5,134 full-period unbalanced. The figure
caption now says so explicitly and notes that the resemblance misled us during
analysis.

**Cell occupancy.** 7,084 non-empty cells is now given against the 22,080
possible (32.1 %).

**The 2 % cohort threshold was ours.** It appeared in a figure as though it
were a standard. The reference line is removed, and the text now states it is a
working convention with no source, adding that the expected number of returning
pre-shock reviewers is below one at the observed rates, so nothing turns on
where the threshold sits.

**Unrun analyses are now listed explicitly** rather than left to be inferred:
no Kaplan–Meier or Cox fit, no PELT comparison, no transformer baseline, and 30
bootstrap replicates where 999 is standard.

## Added

**Section 6.2, "What data would make this estimable."** Inverting the bound
turns the negative result into a specification: UPjT/m reviews within the
panel, plus repeat observation, item-centric sampling, and documented
intervention dates. A worked example gives 135,000 reviews for a modest
five-aspect design, roughly twice the panel assembled from 19.3 million
interactions.

## Not accepted

**"Mohaweesh" and "Tsoros" misspellings.** The file reads Mohawesh and Tsiros.
Both correct already.

**"Figure 6 missing, Figure 2/3 misnumbered."** Eleven figures render in
numerical order. This appears to be an artefact of PDF text extraction on the
reviewer's side.

## Still open, needs runs

1. Kaplan–Meier on the 20 episodes, and an attempted Cox fit.
2. PELT on a subset, compared against the null.
3. 999 bootstrap replicates in place of 30.
4. Block-length sensitivity at 3, 6 and 12 months.
5. Confidence intervals on the observed-to-null ratios.
6. A transformer or LLM extractor on a sample, to estimate m empirically.

Items 3 to 5 are cheap and would close the statistical objections. Item 6 is
the one a referee in NLP will press hardest.
