# ln_test_data

Normalized input layer: every sample's files under the same names, so tests and
scripts do not have to know the company's naming scheme.

```text
ln_test_data/<dataset>/<sample>/
  reads.fastq
  reference.self.fa
  reference.wt.fa
  consensus.N.fa
  variants.N.xlsx
  sanger.N.ab1
  meta.tsv
```

## These files are generated, not authored

`manifest.tsv` (201 rows) records, for every file here, which file under
`01_data/test_data/` it comes from.

## After cloning: run this once

The `.fastq`, `.xlsx` and `.ab1` files are **byte-for-byte copies** of their
`test_data/` originals and together account for ~40 MB, so they are not
committed (see `.gitignore` in this directory). Create them with:

```bash
Rscript 03_dependence/r-environment/materialize_test_data.R
```

The script copies each file listed in `manifest.tsv` and verifies every one by
md5. It exits non-zero and names the offending files if anything is missing or
wrong, so it cannot silently leave a half-populated tree. A successful run ends
with:

```text
ALL ln_test_data LINKS RESOLVE TO THE CORRECT CONTENT
```

It also repairs the state a Windows clone leaves behind when Developer Mode is
off: `git` then writes each link as a ~100 byte text file holding the target
path instead of a real symlink, and the script replaces those stubs with real
copies.

## The .fa files stay in Git

`*.fa` is deliberately not ignored: those files are *not* byte copies. They are
re-parsed from the company's `.seq` / `.ab1` deliverables, so `materialize`
could only copy them, never rebuild them. They are also tiny (98 files, under
100 KB total).

## Regenerating the whole layer

After changing `test_data/` or adding a dataset:

```bash
Rscript 02_code/r/inst/scripts/prepare_test_data.R            # links + manifest
Rscript 03_dependence/r-environment/materialize_test_data.R   # copies
```

`test_data/` is never modified. It is the single source of truth.
