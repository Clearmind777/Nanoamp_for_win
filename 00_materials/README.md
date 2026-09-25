# 00_materials

Planning documents and work reports for the nanoamp project.

Work reports are **historical logs** and are kept verbatim: they describe work
done on the original single repository, before it was split into this Windows
variant and the Linux variant
(`a_09_18_26_mapping_programs_dev_for_linux`). References in reports 1-6 to
Linux tooling, WSL or conda therefore describe past state, not this repository.

```text
00_materials/
|-- programs_dev_info.md       # original brief and requested deliverables
|-- programs_dev_plan_1.md     # development plan (v1)
|-- tutorial.md                # end-user tutorial: GUI, CLI, R package, dependencies
`-- work_reports/
    |-- work_report.1.md       # R core algorithms A/B/C
    |-- work_report.2.md       # directory refactor and DECIPHER mode B
    |-- work_report.3.md       # R package, tutorial and CLI
    |-- work_report.4.md       # R-only route, dependency guide and GUI v1
    |-- work_report.5.md       # bundled dependencies and cross-platform compatibility
    |-- work_report.6.md       # GitHub remote, Windows minimap2 build, local R regression
    |-- work_report.7.md       # Windows/Linux repository split and offline verification
    |-- work_report.8.md       # Python/Tkinter desktop window and exe packaging
    |-- work_report.9.md       # three deliverables separated, install.exe, user README
    |-- work_report.10.md      # install location choice, optional shortcut, uninstall.exe
    |-- work_report.11.md      # repository slimming, layout rename, installer window fixes
    |-- work_report.12.md      # local data-layer repair, paths with spaces, doc corrections
    |-- work_report.13.md      # 01_data without a link layer, release assets as zips
    |-- work_report.14.md      # installer: pick an R the bundled packages can actually use
    |-- work_report.15.md      # install without the offline package: pinned versions, mirror
    |                          #   probing, and the minimap2 the online route was missing
    |-- work_report.16.md      # tidy release/: payload at the root, packaging in _build/
    |-- work_report.17.md      # serious tone throughout: UI strings and every README
    |-- work_report.18.md      # drop the empty 04_builds/; rebuild the R package tarball
    |-- work_report.19.md      # installer: retry file copies that Windows has locked
    `-- work_report.20.md      # sync Linux's lead: core fixes, functional annotation, GUI
```

The original request and the requested deliverables are documented in
`programs_dev_info.md`; the overall design is in `programs_dev_plan_1.md`.
