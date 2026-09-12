# Numeric audit

`audit_numbers.py` reads the manuscript and checks it against the values the
analysis produced. It fixes nothing; it reports.

    python audit_numbers.py --tex manuscript.tex

Run it before every submission and after any change to a parameter.

## What it checks

**Internal consistency of the canonical values.** Eight relationships that must
hold: the share equals qualifying over denominator, R equals rows over
denominator, each ratio equals observed over null, Bonferroni equals p times
four, and so on. A failure here means the canonical block itself is wrong,
which is worse than a stale figure in the text.

**Superseded values still present.** Seven values from earlier runs are listed
as forbidden: R = 33.9, the 1.13m and 3.39m bounds derived from it, the 2,151
denominator recovered by division, the 27.8 null mean from the 30-replicate
run, "30 replicates" itself, and the z = -1.33 normal approximation. Each
occurrence is reported as STALE unless it sits in a passage that explicitly
marks it as superseded, in which case it is reported as "noted".

**Canonical values absent from the text.** A registered value that appears
nowhere usually means a section was rewritten and a number dropped out.

## Current status

    8 consistency relations   all hold
    7 forbidden values        4 present, all in "earlier version" passages
    38 registered values      all appear in the text
    0 problems

The four "noted" entries are deliberate: the paper explains where it previously
had a wrong figure, and naming the old value is part of that explanation.

## What it cannot do

It checks the 38 values registered in `CANON`. A number nobody entered there is
invisible to it. A clean report is evidence of consistency across the
registered set, not proof that every number in the paper is right.

## Adding a value

Add it to `CANON` with the command that produced it. If it supersedes something,
add the old value to `FORBIDDEN` with a note saying what replaced it.

## On parameterisation

The obvious next step is to drive the LaTeX from a single constants file so
that a changed parameter propagates automatically, and to generate tables from
the analysis output rather than typing them. That is the right engineering and
it would have prevented the R = 33.9 episode.

It is also, at this point, engineering rather than science. The audit above
gives most of the protection for a fraction of the effort, and the risk of
rebuilding the document tooling is that it becomes its own project. We
recommend running the audit and submitting.
