# Response to the fifth review

## Three reported errors do not exist

The review reports a duplicated Section 5.10, a duplicated conclusion
paragraph, a run-on "8 ConclusionWe set out to...", and a "Tsoros" misspelling.
Checked in both the source and the rendered PDF:

    subsection{Sensitivity} occurrences        1
    "We report this because" occurrences       1
    "SensitivityFigure" run-on present         False
    "ConclusionWe" run-on present              False
    "Tsoros" in PDF                            False
    "Tsiros" in PDF                            True

None of these is present. Run-on headings are a normal artefact of naive PDF
text extraction, which emits a heading and the following paragraph without a
separator, and duplicated-paragraph reports can arise the same way.

This is the fourth consecutive review to report spellings and structural faults
that the file does not contain. We note it because acting on such reports
without checking would introduce real errors into a clean file. Anything
reported as an editorial defect should be verified against the PDF before it is
"fixed".

## Accepted and applied

**Lexicon polarity removed from the abstract and demoted throughout.** On
reflection our earlier reason for deferring this was wrong. We had said we
would wait for the 999-replicate run, but the reason to demote the measure is
that it is unvalidated, and that holds whatever the replicate count shows.
The abstract now reports star ratings alone: 23 shocks against 27.8 +/- 3.6,
ratio 0.83. The lexicon result is described as a robustness check that agrees.

**Table 3 restructured.** Column headers now carry "(primary)" and "(robustness
only)". Rows are grouped under "Detection" and "Null comparison". The caption
states that the star-rating column requires no extraction model and no
annotation, and that no conclusion rests on the lexicon column.

**Results text reframed** to read the null comparison from star ratings alone.

**Figure 10 caption** now gives episode counts (23 and 29) and points to the
section explaining why star ratings produced no non-recovered episode.

**Table 5 footnote** now explains why Amazon shows n.t. for aspect cells: the
density bound rules out any aspect reaching threshold at R = 6.9, before
extraction quality enters at all.

## Still open: three analyses awaiting execution

`code/followup_analyses.py` implements Kaplan-Meier, PELT against the same
null, and the 999-replicate bootstrap with empirical p-values, ratio intervals,
and block-length sensitivity. 22 self-tests pass. It has not been run against
the data.

    python code/followup_analyses.py --selftest
    python code/followup_analyses.py --scan 500000 --presence 0.75 --reps 999

The reviewer is right that "moot once detection failed" is weak for PELT: count
and location are different questions. The script answers the location question
rather than arguing it away.
