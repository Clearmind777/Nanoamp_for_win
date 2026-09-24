# 04_builds

Build artifacts. Everything in this directory is reproducible and ignored by
Git except this README.

```text
04_builds/
`-- r/
    |-- nanoamp_<version>.tar.gz   # R CMD build output
    `-- nanoamp.Rcheck/        # R CMD check output
```

Rebuild:

```bash
make check
```

Remove build artifacts:

```bash
make clean-builds
```
