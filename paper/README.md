# Aspect-Level Sentiment Recovery Is Not Estimable from Public Review Corpora

Manuscript, figures, and analysis code.
Repository: https://github.com/ssvakil/aspect-recoverability

## Contents

    manuscript.tex / .pdf   18 pages, 11 figures, 5 tables, 52 references
    make_figures.py         regenerates every figure; 30 consistency checks
    figures/                11 PDF figures
    code/                   six analysis scripts, 155 self-tests in total

## Build

    pip install pandas numpy scipy matplotlib
    python make_figures.py --selftest
    python make_figures.py --outdir figures
    pdflatex manuscript.tex && pdflatex manuscript.tex

## Reproducing the analysis

    pip install datasets pyarrow huggingface_hub

    python code/load_amazon.py --category All_Beauty --scan 300000 --products 200
    python code/feasibility_pilot.py --data pilot_data.parquet --category All_Beauty --sample 100000
    python code/balanced_panel_check.py --scan 500000
    python code/category_shock_run.py --scan 500000 --presence 0.75
    python code/aspect_level_run.py --scan 500000 --presence 0.75

Every script accepts `--selftest` and should be run with it first. A failure
there indicates an environment problem, not a data problem.

Amazon Reviews 2023 keeps reviews as JSONL under `raw/review_categories/`; the
loader discovers the path rather than assuming it, and refuses to fall back to
the metadata file of the same category name.

## Provenance of every number

`make_figures.py` holds an `OBSERVED` block naming the generating command for
each value. The self-tests assert internal consistency: outcome counts sum to
shock counts, stated null ratios equal observed divided by null mean, the
sensitivity grid is monotone, per-aspect cells sum to the reported total, and
repeat rates match their raw counts.

No number in the manuscript was estimated, rounded from memory, or carried over
from an earlier draft.

## Before submission

1. Section 5.2 refers to "a second Amazon extract, from a category with heavier
   reviewing than All_Beauty". Name the category from the run log. A marked
   LaTeX comment sits at that line. Do not guess.
2. Two bibliography entries carry `% [check]`; confirm volume and pages.
3. Remove `\linenumbers` for camera-ready.
4. Reformat to the target journal's template.
5. Section 2.3 states plainly that the literature search was targeted, not
   systematic. Either upgrade it to PRISMA or leave the qualification in place.
