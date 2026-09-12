# Aspect-Level Sentiment Decline and Return Is Not Estimable from Two Large Public Review Corpora

Replication package for a negative feasibility study with a density bound.

**Authors:** S. Vakil ([0009-0009-1336-5045](https://orcid.org/0009-0009-1336-5045)),
Y. Farjami ([0000-0003-1908-8826](https://orcid.org/0000-0003-1908-8826))
Department of Computer Engineering, University of Qom

---

## What this study found

We asked whether aspect-level sentiment recovery can be estimated at all from
public review corpora, and concluded that on the two corpora examined it
cannot.

| Finding | Value |
|---|---|
| Amazon product-months meeting a 30-mention threshold | 313 of 11,925 (2.6 %) |
| Shocks detected at the Amazon product level | 0 |
| Aspect cells reaching the threshold on the MobileRec panel | 0 of 7,084 |
| Median mentions per aspect cell | 1 |
| Density bound at T = 30 | j ≤ 1.16m (MobileRec), 0.23m (Amazon) |
| Repeat reviewing of the same item | 0.159 % (Amazon), 0.063 % (MobileRec) |
| Threshold rule, observed vs block bootstrap null | 23 vs 28.4 ± 3.8, p = 0.95 |
| PELT, observed vs the same null | 6 vs 1.77 ± 1.35, p = 0.015; 0.060 after Bonferroni |
| Positive control, false positive rate | 0.93 of clean synthetic series |

The density bound is the transferable part. Before designing an aspect-level
temporal study, divide the reviews your panel will hold by (units × periods ×
aspects) and compare against whatever mention threshold your analysis needs. If
the quotient falls short, no choice of extractor or model will rescue the
design.

## Layout

```
manuscript.tex        source, 28 pages
manuscript.pdf        compiled
make_figures.py       regenerates all 12 figures; holds the observed values
audit_numbers.py      checks the manuscript against those values
requirements.txt      library versions
figures/              12 PDF figures
code/                 nine analysis scripts
protocol/             definitions fixed before data inspection
```

## Requirements

```bash
pip install -r requirements.txt
```

Python 3.12 or 3.13. On 3.14, `dill` breaks `datasets`; installing
`datasets>=5` resolves it. LaTeX needs `mathptmx`, `microtype`, `siunitx`,
`orcidlink`, `placeins`, `lineno`, `natbib`, `authblk`, `booktabs`.

## Reproducing the analysis

Every script accepts `--selftest` and should be run with it first. A failure
there indicates an environment problem, not a data problem.

```bash
# Amazon: density and repeat-review rate
python code/load_amazon.py --category All_Beauty --scan 300000 --products 200
python code/feasibility_pilot.py --data pilot_data.parquet --category All_Beauty --sample 100000

# MobileRec: balanced panel, with denominators logged
python code/balanced_panel_check.py --scan 500000

# Category-level detection
python code/category_shock_run.py --scan 500000 --presence 0.75

# Aspect-level density, the result the title concerns
python code/aspect_level_run.py --scan 500000 --presence 0.75

# Kaplan-Meier, PELT, 999-replicate bootstrap, cohort rates, phi estimation
python code/followup_analyses.py --scan 500000 --presence 0.75 --reps 999

# Detection power and false positive rate on synthetic series
python code/positive_control.py --run
```

Neither corpus is redistributed here. The loaders fetch from the original
distributors, so a reproduction uses the same data or fails loudly if a
distribution has changed. Amazon Reviews 2023 keeps reviews as JSONL under
`raw/review_categories/`; the loader discovers that path rather than assuming
it, and refuses to fall back to the metadata file of the same category name.

## Building the manuscript

```bash
python make_figures.py --selftest
python make_figures.py --outdir figures
pdflatex manuscript.tex && pdflatex manuscript.tex
python audit_numbers.py --tex manuscript.tex
```

Run the audit before every submission and after any parameter change.

## Self-tests

Around 200 assertions across nine scripts. They are not decoration: several
encode failure modes that produce plausible but wrong output, and each was
written because the corresponding mistake was possible.

The ones worth knowing about:

- **Right-censoring.** A permanent decline with fewer than 18 months of
  follow-up must be labelled censored, not non-recovered. Getting this wrong
  inflates apparent irreversibility, and the wrong answer looks reasonable.
- **Null choice.** On a synthetic AR(1) series with no injected shocks, plain
  permutation finds fewer shocks than a circular block bootstrap, because
  permutation destroys the autocorrelation that sets the detection threshold. A
  permutation null therefore favours the alternative. The test demonstrates the
  bias numerically.
- **Turnover.** A constructed case where the population mean recovers while the
  original cohort does not must be flagged as turnover rather than recovery.
- **Path matching.** The loaders must never load `meta_All_Beauty.jsonl` when
  asked for `All_Beauty.jsonl`. Both parse cleanly; only one contains reviews.
- **Guarded ratios.** When the denominator approaches zero the recovery
  attribution ratio is withheld rather than reported. A naive ratio in that
  regime returns 0.53, which looks like a result and is noise.

## Numeric audit

`audit_numbers.py` holds 46 canonical values with the command that produced
each, eight relationships that must hold among them, and a list of superseded
values that must not reappear in the text except where explicitly marked as
historical.

It exists because the same failure occurred four times: a value corrected in
one place and left stale in another. R was corrected to 34.8 in one section and
left at 33.9 in seven others; the false positive rate was updated in a table
and not in the prose above it. The audit catches that kind. It cannot catch a
claim about the code written from memory of the code, which was the fourth
instance.

## Protocol and revision record

`protocol/` holds the operational definitions, fixed before any data were
inspected. The `REVISION_*.md` files record what each round of review changed
and, where a criticism was wrong, why. Several document errors of ours:

- An early draft reported a confidence interval computed from a denominator
  recovered by division, then removed the denominator as underivable and left
  the interval standing.
- A reference was cited as "Jiang, S., et al."; the first author is Xia.
- We argued that testing more PELT penalties would only tighten the multiple
  comparison correction. That reasoning was wrong and the sweep was run.

## Outstanding

**m is not measured.** The density bound is linear in m, the mean distinct
aspects named per review, and every single-number statement in the paper sets
m = 1. `code/annotation_tools.py sample` generates a blind, stratified
annotation sheet; filling it estimates m and validates the lexicon in one pass.
The sheet is generated and unfilled.

This is the one outstanding item that would change a result rather than a
presentation.

## Citation

```bibtex
@unpublished{vakil2026aspect,
  author = {Vakil, S. and Farjami, Y.},
  title  = {Aspect-Level Sentiment Decline and Return Is Not Estimable from
            Two Large Public Review Corpora: A Negative Feasibility Study
            with a Density Bound},
  year   = {2026},
  note   = {Manuscript. Replication package:
            \url{https://github.com/ssvakil/aspect-recoverability}}
}
```

## Licence

Code: MIT. Manuscript and protocol documents: CC BY 4.0. Neither corpus is
redistributed; each remains under its distributor's terms.
