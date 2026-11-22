# Proposal: test a pattern on its own terms first

**Status:** proposal from an outside checker. The three direction points below were confirmed by the project owner on 2026-11-22. The proposed rule itself is not yet adopted.

## Context

The project's working hypothesis is stated in the continuum essay ([continuum PR #1](https://github.com/Foundation-0/continuum/pull/1), `continuum.md`, lines 2 to 3). Our knowledge is limited by the habit of sorting reality into classes and fixed structures. Reality is a continuum, so a fixed structure will always miss part of it.

Direction given to the team on 2026-11-21, confirmed by the project owner on 2026-11-22:

1. The existing approach to mathematics, down to its number systems and notation, is assumed to be flawed in a way that keeps us from capturing reality.
2. The team may derive its own symbols and mathematical systems where that is what it takes to represent the patterns it finds.
3. Patterns are to be looked for by observing raw sensor data from high quality sources such as NASA, without leaning on existing theorems or accepted knowledge.

## What the method lacks today

Law 4 and Gate 9 (`spec/LAWS_AND_GATES.md`, lines 15 and 57) count a result as known until prior work has been read in full. Law 5 and Gate 5 (lines 16 and 53) accept a cross-field claim only with typed objects and a map that runs. Both judge a claim against existing knowledge. Apart from the null tests in Gate 3 (line 51), nothing in the method scores a pattern that has no theory to compare against.

## Proposed rule: own terms first

1. **Two phases, kept apart.** Phase 1 tests a pattern on its own terms. Rerun it from the raw source, try it on data the finder never saw, and try it on a second instrument. Phase 2 compares it with existing mathematics, later and separately. "Already known" and "does not translate" are both recorded in phase 2. Neither is a verdict on phase 1.
2. **New symbols are judged by use.** Can another party, given only the symbol's rules and the raw data, get the same pattern? Does the symbol then say something right about data it has not seen? A glyph that stands for a standard construct and adds no rule of its own is a renaming, and is recorded as one.
3. **The essay's own standard is the acceptance rule.** The essay says what is real is "the invariant that survives every change of net" (line 3). A signature counts only if it survives changes of sampling rate, quantisation, amplitude scale, window and instrument.
4. **Two checks stay, because they need no theorem.** Scrambled data must not show the pattern. The pattern must show up in data the finder did not look at.
5. **A signature that shows up everywhere is not a finding.** Include controls where it should be absent.
6. **Where a claim gives nothing measurable, hand it back to its authors for a definition.** Do not invent one and then knock it down.

## Why the two checks matter more under this hypothesis, not less

- Pattern-finding is itself the classifying habit the hypothesis distrusts, so an unchecked pattern is that habit at work.
- A model cannot look "without reference to current knowledge", because that knowledge is what it is made of.
- New symbols can hide a rediscovery even from the people who coined them.

## The hypothesis can be tested directly

A new symbol system is still a definite structure, so by the hypothesis it will fail too. What matters is how it fails.

If fixed structures always miss part of a continuum, the best fixed description of a rich dataset should leave a remainder that is not noise: structure that recurs in unseen data and is absent in scrambled copies. A positive result would be evidence for the hypothesis itself, not just for one pattern.

## Worked example

The outside check of the eight-way unification claim ([cave-expedition PR #5](https://github.com/Foundation-0/cave-expedition/pull/5)) was first reported as "the claim fails as worded". The sharper reading is that the borrowed label failed. "Schur complement" was too loose, since any block system passes, and too rigid, since the tropical and non-Hermitian rows fall outside it.

What survived is a bridge between two kinds, not a class. Ordinary and tropical elimination agree exactly when nothing cancels, and when something cancels the gap can be measured.

## First application

The pre-registration in [cave-expedition PR #6](https://github.com/Foundation-0/cave-expedition/pull/6) applies this rule to the essay's line 16, which says raw telemetry "reveals the same four universal transformations".
