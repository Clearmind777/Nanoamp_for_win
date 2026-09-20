# tmp/test_results

Run outputs. Everything here is reproducible and ignored by Git except this
README.

```text
tmp/test_results/
|-- r/                 # R package / CLI / GUI test runs
|-- cli/               # CLI smoke examples
|-- gui/               # Python GUI runs
`-- _archive/          # older runs kept locally for reference
```

Conventions:

- one subdirectory per run;
- core outputs follow `02_code/shared/docs/output_schema.md`;
- older runs are moved to `_archive/` instead of being deleted;
- build artifacts belong in `04_builds/`, not here.

The directory deliberately holds small files only. Test data lives in
`01_data/`, and anything large should be reproducible from a run rather than
committed.
