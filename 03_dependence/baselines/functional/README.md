# Functional regression baseline

`comparison.tsv`, `summary_by_mode.tsv` and `run_index.tsv` here are a snapshot
of a known-good functional regression over the real datasets in `01_data/`
(168 runs = 3 datasets × samples × modes A/B/C × self/wt references).

```
make functional-test       # run the regression, then compare with this baseline
make functional-baseline   # re-run and overwrite this baseline (review the diff!)
```

`check_functional_baseline.R` compares every run row by row: `status`,
per-run variant counts, `top1_variants`, `n_reads_*`, `mapping_rate`,
`mean_identity` and `top1_proportion` (the last three with a 1e-6 tolerance).
A run that used to be `ok` and no longer is fails the check outright.

## Why this baseline is meaningful

Mode B (de novo clustering) calls `DECIPHER::Clusterize`, which is stochastic:
with identical input it returned different cluster sizes on consecutive calls
(measured: 38/38/35 clusters for the same 437 reads, even with
`processors = 1`). Before `clustering_seed` was introduced, every Mode B row
differed between runs and this baseline could only have been advisory. nanoamp
now seeds that call, so the whole baseline - Mode B included - is reproducible
byte for byte; the check was verified by running the regression twice with the
same build and getting `FUNCTIONAL BASELINE MATCHED`.

## Regenerating

The baseline is machine-dependent only in `elapsed_sec` (which is not compared).
Regenerate it when a behaviour change is intended, and say so in the commit
message and in the work report: the diff is the evidence of what changed.
