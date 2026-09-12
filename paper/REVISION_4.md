# Response to the fourth review

Three conditions were set for acceptance. One is closed, one is ready to close
and needs a run, one is deferred until that run completes.

## Condition 3 — table ambiguity: closed

Table 2's `n.r.` entries now carry bounds rather than an unexplained marker.
For the balanced panels the denominator lies between the qualifying count and
the 46 x 48 = 2,208 maximum. We give the interval instead of recovering a point
value by division, and note that a re-run with denominator logging would close
it. The code to do so is in the repository.

## Condition 1 — three unrun analyses: script written, awaiting execution

`code/followup_analyses.py` implements all three, with 22 self-tests:

- **Kaplan-Meier** with Greenwood variance and log-log confidence limits.
  Linear limits run outside [0,1] at this sample size and invite over-reading.
  Censored episodes are censored at their own follow-up length rather than at
  the horizon, which is the distinction the whole design rests on and which has
  a dedicated test.
- **PELT** with an L2 cost, using `ruptures` when present and a direct
  implementation otherwise, so the check cannot silently fail to run. Change
  point counts are compared against the same block bootstrap null. The referee
  is right that count and location are different questions.
- **999 replicates** with an empirical p-value under the (b+1)/(B+1)
  correction, so p can never be reported as exactly zero. Plus a percentile
  interval on the observed-to-null ratio and a block-length sensitivity check
  at 3, 6 and 12 months.

Run with:

    python code/followup_analyses.py --selftest
    python code/followup_analyses.py --scan 500000 --presence 0.75 --reps 999

## Condition 2 — lexicon in the abstract: deferred, deliberately

The referee recommends removing lexicon polarity from the abstract and main
results, keeping star ratings alone. We agree with the reasoning and will do
it, but not before the 999-replicate run. If the empirical p-values differ
materially from the normal approximations now reported, both measures need
re-reading, and demoting one of them first would mean deciding which result to
foreground before knowing what the results are.

## Corrected in this round

**A miscited reference.** The TKDD paper was cited as "Jiang, S., et al.
(2021)". The first author is Xia, and the Jiang initial was also wrong. Correct
entry: Xia, P., Jiang, W., Wu, J., Xiao, S., Wang, G. (2021), ACM TKDD 15(4),
Article 68, 1-29. This was our error, not a formatting slip.

**Figure 3 caption** now shows the arithmetic (30k x 46 x 48, giving 662,400 at
k = 10) and the exact panel size, 74,780 rather than "75k".

**Figure 2 caption** now names the episode counts: five, 20, 19.

**Figure 11 caption** now states that no grid cell was significant against the
null, which the text said but the caption did not.

**The replicate shortfall** is now described precisely: it does not change the
direction of the conclusion but does limit p-value precision, which is why the
values rest on a normal approximation.

## Not accepted

Reported typos "Kezough", "stations", "Tsoros" and a run-together heading at
Section 5.10. The source reads Kezouh, statins, Tsiros, and the heading is on
its own line. This is the third review to report spellings that are already
correct, which suggests PDF text extraction on the reviewing side rather than
an error in the file.
