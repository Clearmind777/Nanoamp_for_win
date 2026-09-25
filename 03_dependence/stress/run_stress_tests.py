"""Environment stress tests for the Windows build (plan section 6, groups A-D).

Every case runs the *real* CLI through the same runner the GUI uses, so what is
verified here is what a user gets. Cases that cannot be automated on a single
machine (disk full, ARM64, antivirus, high DPI) are reported as SKIP with the
reason and the manual procedure, never as a pass - see results.tsv.

    python 03_dependence/stress/run_stress_tests.py --group A,B,C,D
    python 03_dependence/stress/run_stress_tests.py --group A --keep

Groups:
    A  network, proxy, cache (needs internet for some cases)
    B  input degeneracy and annotation-matrix shape
    C  environment: paths, cache resolution, missing curl, no PATH help
    D  cancellation and concurrency
"""
from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
from contextlib import contextmanager
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parent.parent
sys.path.insert(0, str(REPO / "02_code" / "PythonGUI"))

from nanoamp_gui.r_runner import NanoampRunner  # noqa: E402

DATA = HERE / "data"
ZNF8_FASTA = DATA / "znf8_exon_amplicon.fa"
ZNF8_META = DATA / "znf8_exon_amplicon.json"

# A port nothing listens on: pointing the proxy variables at it makes every
# HTTP request fail immediately, which is how "no network" is simulated without
# touching the machine's firewall.
DEAD_PROXY = "http://127.0.0.1:9"

RESULTS: list[dict[str, str]] = []


def record(group: str, case: str, status: str, detail: str) -> None:
    RESULTS.append({"group": group, "case": case, "status": status,
                    "detail": detail.replace("\n", " ")[:400]})
    mark = {"PASS": "OK  ", "FAIL": "FAIL", "SKIP": "SKIP"}[status]
    print(f"   {mark} {case}: {detail}".rstrip())


def check(group: str, case: str, ok: bool, detail: str = "") -> bool:
    record(group, case, "PASS" if ok else "FAIL", detail)
    return ok


@contextmanager
def patched_env(**values: str | None):
    """Set/remove environment variables for the child processes we spawn."""
    old = {k: os.environ.get(k) for k in values}
    try:
        for key, value in values.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value
        yield
    finally:
        for key, value in old.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value


def path_without(tool_exe: str) -> str:
    """PATH minus every directory that contains `tool_exe`."""
    keep = []
    for part in os.environ.get("PATH", "").split(os.pathsep):
        if not part:
            continue
        try:
            if (Path(part) / tool_exe).is_file():
                continue
        except OSError:
            pass
        keep.append(part)
    return os.pathsep.join(keep)


def read_manifest(outdir: Path) -> dict:
    path = Path(outdir) / "run_manifest.json"
    if not path.is_file():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


def read_qc(outdir: Path) -> dict[str, str]:
    path = Path(outdir) / "qc.tsv"
    if not path.is_file():
        return {}
    out: dict[str, str] = {}
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines()[1:]:
        key, _, value = line.partition("\t")
        out[key] = value
    return out


def read_tsv(path: Path) -> tuple[list[str], list[dict[str, str]]]:
    if not Path(path).is_file():
        return [], []
    lines = Path(path).read_text(encoding="utf-8", errors="replace").splitlines()
    if not lines:
        return [], []
    fields = lines[0].split("\t")
    rows = [dict(zip(fields, line.split("\t"))) for line in lines[1:] if line.strip()]
    return fields, rows


def count_cache_files(cache_dir: Path) -> int:
    if not Path(cache_dir).is_dir():
        return 0
    return sum(1 for p in Path(cache_dir).rglob("*") if p.is_file())


def make_offline_fixture(root: Path, cds_start: int = 40, cds_end: int = 159,
                         mutate: bool = True) -> dict[str, Path]:
    """A small amplicon with an in-frame CDS and a few interesting haplotypes.

    No aligner is needed to *build* it; the runs use --aligner r so the fixture
    is independent of the bundled minimap2.
    """
    root.mkdir(parents=True, exist_ok=True)
    bases = "ACGT"
    import random
    rng = random.Random(20260926)
    seq = []
    while len(seq) < 300:
        b = rng.choice(bases)
        if len(seq) >= 2 and seq[-1] == b == seq[-2]:
            continue
        seq.append(b)
    ref = "".join(seq)
    chars = list(ref)

    def mutate_at(text: str, pos: int, alt: str) -> str:
        x = list(text)
        x[pos - 1] = alt
        return "".join(x)

    alt = "T" if chars[cds_start + 20 - 1] != "T" else "A"
    snv = mutate_at(ref, cds_start + 20, alt)
    frameshift = ref[: cds_start + 30 - 1] + ref[cds_start + 30:]
    reads = [ref] * 40
    if mutate:
        reads += [snv] * 20 + [frameshift] * 10
    rng.shuffle(reads)

    fa = root / "ref.fa"
    fa.write_text(">stress_amplicon\n" + ref + "\n", encoding="utf-8")
    fq = root / "reads.fastq"
    with fq.open("w", encoding="utf-8") as fh:
        for i, s in enumerate(reads):
            fh.write(f"@read{i}\n{s}\n+\n{'I' * len(s)}\n")
    cfg = root / "cds.json"
    cfg.write_text(json.dumps({
        "name": "stress_cds", "route": "cds", "genetic_code": "Standard",
        "cds": {"start": cds_start, "end": cds_end, "strand": "+",
                "frame": 0, "boundaries": "inclusive"},
    }, indent=2), encoding="utf-8")
    return {"dir": root, "ref": fa, "reads": fq, "cfg": cfg}


def znf8_reads(work: Path, mutations=(50, 120)) -> Path:
    """Reads built from the committed GRCh38 slice (group A fixtures)."""
    lines = ZNF8_FASTA.read_text(encoding="utf-8").splitlines()
    ref = lines[1].strip().upper()
    chars = list(ref)
    reads = [ref] * 60
    for pos in mutations:
        alt = "A" if chars[pos - 1] != "A" else "C"
        x = list(ref)
        x[pos - 1] = alt
        reads += ["".join(x)] * 20
    fq = work / "znf8_reads.fastq"
    with fq.open("w", encoding="utf-8") as fh:
        for i, s in enumerate(reads):
            fh.write(f"@z{i}\n{s}\n+\n{'I' * len(s)}\n")
    return fq


# ---------------------------------------------------------------------------
# Group A: network, proxy, cache
# ---------------------------------------------------------------------------

def group_a(runner: NanoampRunner, work: Path) -> None:
    if not ZNF8_FASTA.is_file():
        record("A", "fixture", "SKIP", f"{ZNF8_FASTA} missing")
        return
    reads = znf8_reads(work)
    cfg = work / "genome.json"
    cfg.write_text(json.dumps({"name": "stress_genome", "route": "genome",
                               "genetic_code": "Standard"}, indent=2), encoding="utf-8")
    cache = work / "cache"

    # A1: plain online run, cold cache.
    out = work / "a1"
    cache.mkdir(parents=True, exist_ok=True)
    with patched_env(NANOAMP_CACHE_DIR=str(cache), NANOAMP_NO_CACHE=None):
        code, lines = runner.run([
            "call", "--reads", str(reads), "--reference", str(ZNF8_FASTA),
            "--outdir", str(out), "--mode", "A", "--aligner", "r",
            "--annotate-config", str(cfg), "--annotation-detail",
        ])
    qc = read_qc(out)
    fields, rows = read_tsv(out / "annotation.tsv")
    ok = (code == 0 and rows and qc.get("annotation_source") == "ensembl-rest"
          and qc.get("ensembl_release") and qc.get("n_transcripts_annotated") == "1")
    check("A", "A1 online genome route (cold cache)", ok,
          f"exit={code} transcripts={qc.get('n_transcripts_annotated')} "
          f"rows={len(rows)} release={qc.get('ensembl_release')}")
    consequences = sorted({r.get("consequence_en", "") for r in rows})
    check("A", "A1b coding consequences are produced", len(consequences) >= 2,
          f"consequences={consequences}")
    cached_after_a1 = count_cache_files(cache)
    check("A", "A1c the run cached its requests", cached_after_a1 > 0,
          f"{cached_after_a1} cache files")

    # A2: the same run through an explicit HTTP proxy.
    clash = os.environ.get("NANOAMP_STRESS_PROXY", "http://127.0.0.1:7890")
    out2 = work / "a2"
    cache2 = work / "cache_a2"
    with patched_env(NANOAMP_CACHE_DIR=str(cache2), HTTPS_PROXY=clash,
                     HTTP_PROXY=clash, NANOAMP_NO_CACHE=None):
        code2, _ = runner.run([
            "call", "--reads", str(reads), "--reference", str(ZNF8_FASTA),
            "--outdir", str(out2), "--mode", "A", "--aligner", "r",
            "--annotate-config", str(cfg), "--list-transcripts",
        ])
    if code2 == 0:
        check("A", "A2 online route through an explicit proxy", True,
              f"proxy={clash} exit=0")
    else:
        record("A", "A2 online route through an explicit proxy", "SKIP",
               f"proxy {clash} not reachable on this machine (exit={code2})")

    # A3/A8: requests that cannot succeed must fail loudly, not silently.
    out3 = work / "a3"
    with patched_env(NANOAMP_CACHE_DIR=str(work / "cache_a3"), HTTPS_PROXY=DEAD_PROXY,
                     HTTP_PROXY=DEAD_PROXY, NANOAMP_NO_CACHE=None):
        code3, lines3 = runner.run([
            "call", "--reads", str(reads), "--reference", str(ZNF8_FASTA),
            "--outdir", str(out3), "--mode", "A", "--aligner", "r",
            "--annotate-config", str(cfg),
        ])
    info3 = read_manifest(out3)
    check("A", "A4 unreachable Ensembl fails with a non-zero exit", code3 != 0,
          f"exit={code3}")
    check("A", "A4b failure is classified as network",
          info3.get("error_class") == "network", f"error_class={info3.get('error_class')}")
    check("A", "A4c no annotation.tsv is left behind",
          not (out3 / "annotation.tsv").is_file(),
          "annotation.tsv absent" if not (out3 / "annotation.tsv").is_file() else "present!")
    check("A", "A5 the error message is actionable",
          any(("cds" in ln.lower() or "离线" in ln or "--no-cache" in ln or "代理" in ln
               or "network" in ln.lower() or "HTTP request failed" in ln)
              for ln in lines3),
          next((ln for ln in lines3 if "HTTP request failed" in ln or "cds" in ln.lower()),
               "n/a"))
    check("A", "A4d a failed run still leaves a manifest and a log",
          (out3 / "run_manifest.json").is_file() and (out3 / "nanoamp.log").is_file(),
          f"status={info3.get('status')}")

    # A6: a warm cache must let the very same run succeed with no network at all.
    out6 = work / "a6"
    before = count_cache_files(cache)
    with patched_env(NANOAMP_CACHE_DIR=str(cache), HTTPS_PROXY=DEAD_PROXY,
                     HTTP_PROXY=DEAD_PROXY, NANOAMP_NO_CACHE=None):
        code6, lines6 = runner.run([
            "call", "--reads", str(reads), "--reference", str(ZNF8_FASTA),
            "--outdir", str(out6), "--mode", "A", "--aligner", "r",
            "--annotate-config", str(cfg),
        ])
    after = count_cache_files(cache)
    rows6 = read_tsv(out6 / "annotation.tsv")[1]
    check("A", "A6 warm cache replays the run with no network", code6 == 0 and bool(rows6),
          f"exit={code6} rows={len(rows6)}")
    check("A", "A6b the warm run added no new cache entries", after == before,
          f"{before} -> {after} files")
    if rows:
        check("A", "A6c the cached result equals the online result",
              [r.get("consequence_en") for r in rows6] ==
              [r.get("consequence_en") for r in rows],
              "identical consequences")

    # A7: a corrupted cache entry must not crash the run or be trusted.
    corrupted = 0
    for path in sorted(p for p in cache.rglob("*") if p.is_file()):
        try:
            path.write_text("{ this is not a valid cached response", encoding="utf-8")
            corrupted += 1
        except OSError:
            pass
        if corrupted >= 3:
            break
    out7 = work / "a7"
    # Proxy variables are left as they are: this case is about a corrupted
    # cache, so the network must stay reachable (it is A4/A6 that block it).
    with patched_env(NANOAMP_CACHE_DIR=str(cache), NANOAMP_NO_CACHE=None):
        code7, lines7 = runner.run([
            "call", "--reads", str(reads), "--reference", str(ZNF8_FASTA),
            "--outdir", str(out7), "--mode", "A", "--aligner", "r",
            "--annotate-config", str(cfg),
        ])
    info7 = read_manifest(out7)
    rows7 = read_tsv(out7 / "annotation.tsv")[1]
    identical = [r.get("consequence_en") for r in rows7] == \
        [r.get("consequence_en") for r in rows]
    # Acceptable: it recovered (and produced the same answer as A1), or it
    # refused loudly. Silently different results would not be acceptable.
    benign = (code7 == 0 and bool(rows7) and identical) or (
        code7 != 0 and info7.get("error_class") in ("network", "internal"))
    check("A", "A7 a corrupted cache is survived (refetch or loud error)", benign,
          f"exit={code7} class={info7.get('error_class')} rows={len(rows7)} "
          f"same_as_a1={identical} ({corrupted} entries corrupted)")

    # A9: --no-cache must not read or write (and must not delete) the cache.
    out9 = work / "a9"
    before9 = count_cache_files(cache)
    with patched_env(NANOAMP_CACHE_DIR=str(cache), NANOAMP_NO_CACHE=None):
        code9, _ = runner.run([
            "call", "--reads", str(reads), "--reference", str(ZNF8_FASTA),
            "--outdir", str(out9), "--mode", "A", "--aligner", "r",
            "--annotate-config", str(cfg), "--no-cache",
        ])
    after9 = count_cache_files(cache)
    check("A", "A9 --no-cache bypasses the cache without destroying it",
          after9 >= before9 and cache.is_dir(),
          f"exit={code9} {before9} -> {after9} files (corrupted entries still present)")

    # B2: --transcript all exercises the multi-transcript path.
    out_all = work / "b2"
    with patched_env(NANOAMP_CACHE_DIR=str(cache), NANOAMP_NO_CACHE=None):
        code_all, _ = runner.run([
            "call", "--reads", str(reads), "--reference", str(ZNF8_FASTA),
            "--outdir", str(out_all), "--mode", "A", "--aligner", "r",
            "--annotate-config", str(cfg), "--transcript", "all",
        ])
    qc_all = read_qc(out_all)
    skipped = qc_all.get("n_transcripts_skipped", "0")
    annotated = qc_all.get("n_transcripts_annotated", "0")
    check("B", "B2 --transcript all annotates every overlapping transcript",
          code_all == 0 and int(annotated or 0) >= 1
          and (out_all / "annotation.tsv").is_file(),
          f"exit={code_all} annotated={annotated} skipped={skipped}")
    if int(skipped or 0) > 0:
        info_all = read_manifest(out_all)
        drops = (info_all.get("annotation") or {}).get("skipped_transcripts") or []
        check("B", "B2b every dropped transcript is recorded with a reason",
              len(drops) >= 1 and all(d.get("problem") for d in drops),
              f"{len(drops)} skipped, e.g. {drops[0].get('problem', '')[:60]}" if drops else "none")

    # D3: two concurrent online runs sharing one cache must both succeed and
    # leave the cache usable.
    cache_d = work / "cache_d"
    out_d1, out_d2 = work / "d3_1", work / "d3_2"

    def concurrent_run(outdir: Path):
        return runner.run([
            "call", "--reads", str(reads), "--reference", str(ZNF8_FASTA),
            "--outdir", str(outdir), "--mode", "A", "--aligner", "r",
            "--annotate-config", str(cfg),
        ])

    import threading
    results: dict[int, int] = {}

    with patched_env(NANOAMP_CACHE_DIR=str(cache_d), NANOAMP_NO_CACHE=None):
        threads = []
        for i, outdir in enumerate((out_d1, out_d2), start=1):
            def target(idx=i, od=outdir):
                code, _ = concurrent_run(od)
                results[idx] = code
            t = threading.Thread(target=target)
            threads.append(t)
            t.start()
        for t in threads:
            t.join()
    both_ok = results.get(1) == 0 and results.get(2) == 0
    check("D", "D3 two concurrent runs sharing a cache both succeed", both_ok,
          f"exits={results}")
    # the cache must still be usable afterwards
    out_d3 = work / "d3_after"
    with patched_env(NANOAMP_CACHE_DIR=str(cache_d), HTTPS_PROXY=DEAD_PROXY,
                     HTTP_PROXY=DEAD_PROXY, NANOAMP_NO_CACHE=None):
        code_after, _ = runner.run([
            "call", "--reads", str(reads), "--reference", str(ZNF8_FASTA),
            "--outdir", str(out_d3), "--mode", "A", "--aligner", "r",
            "--annotate-config", str(cfg),
        ])
    check("D", "D3b the shared cache is not corrupted by concurrency",
          code_after == 0, f"offline replay of the concurrent cache: exit={code_after}")


# ---------------------------------------------------------------------------
# Group B: input degeneracy
# ---------------------------------------------------------------------------

def group_b(runner: NanoampRunner, work: Path) -> None:
    fx = make_offline_fixture(work / "b")

    # B1: the offline route's outputs match the documented schema.
    out = work / "b1"
    code, _ = runner.run([
        "call", "--reads", str(fx["reads"]), "--reference", str(fx["ref"]),
        "--outdir", str(out), "--mode", "A", "--aligner", "r",
        "--annotate-config", str(fx["cfg"]), "--annotation-detail",
    ])
    fields, rows = read_tsv(out / "annotation.tsv")
    qc = read_qc(out)
    expected = ["haplotype_id", "transcript_id", "cds_ok", "protein_change",
                "consequence_en", "consequence_zh", "consequence_any_transcript",
                "transcript_conflict"]
    check("B", "B1 offline cds annotation matches the documented schema",
          code == 0 and all(f in fields for f in expected) and qc.get("annotation_source") == "cds-config",
          f"exit={code} missing={[f for f in expected if f not in fields]}")
    dfields, drows = read_tsv(out / "variants_annotation.tsv")
    check("B", "B1b variants_annotation.tsv has the documented columns",
          all(f in dfields for f in ("haplotype_id", "type", "genome_pos", "cds_pos",
                                     "codon_ref", "aa_ref", "consequence_en")),
          f"{len(drows)} rows, {len(dfields)} columns")
    consequences = {r.get("consequence_en") for r in rows}
    check("B", "B1c the fixture produces no_variant plus coding consequences",
          "no_variant" in consequences and len(consequences - {"no_variant"}) >= 1,
          f"{sorted(consequences)}")
    # The reference haplotype must be `no_variant`, not `synonymous` (L4).
    ref_rows = [r for r in rows if r.get("variants") == "."]
    check("B", "B1d the reference haplotype is no_variant / p.(=)",
          bool(ref_rows) and all(r.get("consequence_en") == "no_variant"
                                 and r.get("protein_change") == "p.(=)" for r in ref_rows),
          f"{len(ref_rows)} reference rows")

    # B5: a CDS whose length is not a multiple of three is skipped and recorded.
    bad = json.loads(fx["cfg"].read_text(encoding="utf-8"))
    bad["cds"]["end"] = bad["cds"]["start"] + 100     # 101 bp
    bad_cfg = work / "b_bad.json"
    bad_cfg.write_text(json.dumps(bad, indent=2), encoding="utf-8")
    out_bad = work / "b5"
    code_bad, _ = runner.run([
        "call", "--reads", str(fx["reads"]), "--reference", str(fx["ref"]),
        "--outdir", str(out_bad), "--mode", "A", "--aligner", "r",
        "--annotate-config", str(bad_cfg),
    ])
    qc_bad = read_qc(out_bad)
    info_bad = read_manifest(out_bad)
    check("B", "B5 a non-multiple-of-3 CDS is skipped, recorded, exit 0",
          code_bad == 0 and qc_bad.get("annotation_available") == "FALSE"
          and "multiple of 3" in qc_bad.get("annotation_skip_reason", ""),
          f"exit={code_bad} reason={qc_bad.get('annotation_skip_reason', '')[:50]}")
    check("B", "B5b the skip is machine-readable in the manifest",
          info_bad.get("status") == "done"
          and bool((info_bad.get("annotation") or {}).get("skipped_transcripts")),
          f"status={info_bad.get('status')}")
    out_strict = work / "b5_strict"
    code_strict, _ = runner.run([
        "call", "--reads", str(fx["reads"]), "--reference", str(fx["ref"]),
        "--outdir", str(out_strict), "--mode", "A", "--aligner", "r",
        "--annotate-config", str(bad_cfg), "--strict",
    ])
    info_strict = read_manifest(out_strict)
    check("B", "B5c --strict turns that skip into a failure",
          code_strict != 0 and info_strict.get("status") == "failed"
          and bool(info_strict.get("error_message")),
          f"exit={code_strict} status={info_strict.get('status')}")

    # B6: empty and malformed FASTQ.
    empty = work / "empty.fastq"
    empty.write_text("", encoding="utf-8")
    out_e = work / "b6_empty"
    code_e, _ = runner.run(["call", "--reads", str(empty), "--reference", str(fx["ref"]),
                            "--outdir", str(out_e), "--mode", "A", "--aligner", "r"])
    info_e = read_manifest(out_e)
    check("B", "B6 an empty FASTQ fails loudly instead of reporting zero reads",
          code_e != 0 and info_e.get("error_class") == "input",
          f"exit={code_e} class={info_e.get('error_class')} "
          f"msg={str(info_e.get('error_message'))[:60]}")

    malformed = work / "malformed.fastq"
    malformed.write_text("@r1\nACGT\n+\n", encoding="utf-8")   # 3 lines
    out_m = work / "b6_malformed"
    code_m, _ = runner.run(["call", "--reads", str(malformed), "--reference", str(fx["ref"]),
                            "--outdir", str(out_m), "--mode", "A", "--aligner", "r"])
    info_m = read_manifest(out_m)
    check("B", "B6b a malformed FASTQ is rejected with a readable message",
          code_m != 0 and info_m.get("error_class") == "input"
          and "FASTQ" in str(info_m.get("error_message", "")),
          f"exit={code_m} msg={str(info_m.get('error_message'))[:60]}")

    # B4: a long CDS still produces proteins on request.
    long_cfg = json.loads(fx["cfg"].read_text(encoding="utf-8"))
    long_cfg["name"] = "stress_long_cds"
    long_cfg["cds"]["start"] = 1
    long_cfg["cds"]["end"] = 297
    long_cfg_path = work / "b_long.json"
    long_cfg_path.write_text(json.dumps(long_cfg, indent=2), encoding="utf-8")
    out_long = work / "b4"
    code_long, _ = runner.run([
        "call", "--reads", str(fx["reads"]), "--reference", str(fx["ref"]),
        "--outdir", str(out_long), "--mode", "A", "--aligner", "r",
        "--annotate-config", str(long_cfg_path), "--annotation-proteins",
    ])
    lfields, lrows = read_tsv(out_long / "annotation.tsv")
    ok_long = (code_long == 0 and "ref_protein" in lfields and "alt_protein" in lfields
               and any(r.get("ref_protein") for r in lrows))
    check("B", "B4 --annotation-proteins writes reference and alternate proteins", ok_long,
          f"exit={code_long} columns={'ref_protein' in lfields} rows={len(lrows)}")

    # B3: a large annotation matrix (many haplotypes) must not blow up. Mode A
    # is used because Mode C does not annotate at all; every variant therefore
    # gets enough supporting reads (3) to pass the caller's thresholds.
    big = make_big_haplotype_fixture(work / "b3")
    out_big = work / "b3_out"
    t0 = time.time()
    code_big, _ = runner.run([
        "call", "--reads", str(big["reads"]), "--reference", str(big["ref"]),
        "--outdir", str(out_big), "--mode", "A", "--aligner", "r",
        "--annotate-config", str(big["cfg"]), "--annotation-detail",
        "--top-n", "200", "--min-reads", "3", "--min-freq", "0.01",
    ])
    elapsed = time.time() - t0
    bfields, brows = read_tsv(out_big / "annotation.tsv")
    haps = {r.get("haplotype_id") for r in brows}
    check("B", "B3 a large haplotype matrix is annotated without blowing up",
          code_big == 0 and len(haps) >= 15 and elapsed < 300,
          f"exit={code_big} rows={len(brows)} haplotypes={len(haps)} in {elapsed:.0f}s")


def make_big_haplotype_fixture(root: Path) -> dict[str, Path]:
    """Many haplotypes, each with enough supporting reads to be called.

    Mode A (with the R aligner) is used: Mode C does not annotate at all, so a
    Mode C fixture could not exercise the annotation matrix. Each SNV gets three
    reads so it passes the default min_reads threshold.
    """
    root.mkdir(parents=True, exist_ok=True)
    import random
    rng = random.Random(7)
    seq = []
    while len(seq) < 300:
        b = rng.choice("ACGT")
        if len(seq) >= 2 and seq[-1] == b == seq[-2]:
            continue
        seq.append(b)
    ref = "".join(seq)
    chars = list(ref)
    reads = [ref] * 12
    for i in range(1, 41):
        pos = 30 + i
        alt = "A" if chars[pos - 1] != "A" else "C"
        x = list(ref)
        x[pos - 1] = alt
        reads += ["".join(x)] * 3
    fa = root / "ref.fa"
    fa.write_text(">big\n" + ref + "\n", encoding="utf-8")
    fq = root / "reads.fastq"
    with fq.open("w", encoding="utf-8") as fh:
        for i, s in enumerate(reads):
            fh.write(f"@big{i}\n{s}\n+\n{'I' * len(s)}\n")
    cfg = root / "cds.json"
    cfg.write_text(json.dumps({
        "name": "stress_big", "route": "cds", "genetic_code": "Standard",
        "cds": {"start": 31, "end": 300, "strand": "+", "frame": 0,
                "boundaries": "inclusive"},
    }, indent=2), encoding="utf-8")
    return {"dir": root, "ref": fa, "reads": fq, "cfg": cfg}


# ---------------------------------------------------------------------------
# Group C: environment
# ---------------------------------------------------------------------------

def group_c(runner: NanoampRunner, work: Path) -> None:
    # C1: spaces and Chinese characters in every path.
    tricky = work / "含 空格 的 目录" / "样本 A"
    fx = make_offline_fixture(tricky)
    out = tricky / "结果 输出"
    code, lines = runner.run([
        "call", "--reads", str(fx["reads"]), "--reference", str(fx["ref"]),
        "--outdir", str(out), "--mode", "A", "--aligner", "r",
        "--annotate-config", str(fx["cfg"]),
    ])
    rows = read_tsv(out / "annotation.tsv")[1]
    check("C", "C1 paths with spaces and Chinese characters work end to end",
          code == 0 and bool(rows), f"exit={code} rows={len(rows)}")
    manifest = read_manifest(out)
    check("C", "C1b the manifest records the real paths",
          str(manifest.get("reference", {}).get("path", "")).endswith("ref.fa"),
          str(manifest.get("reference", {}).get("path", ""))[-40:])

    # C2: a path longer than MAX_PATH (260 characters). Creating the directory
    # itself may be refused by the OS (which is the interesting half of the
    # case), so the output path is passed without being created: the run must
    # then fail with a message that names the directory rather than crashing.
    deep = work / "longpath"
    node = deep
    while len(str(node)) < 300:
        node = node / "0123456789abcdef0123456789abcdef"
    out2 = node / "out"
    code2, lines2 = runner.run([
        "call", "--reads", str(fx["reads"]), "--reference", str(fx["ref"]),
        "--outdir", str(out2), "--mode", "A", "--aligner", "r",
    ])
    info2 = read_manifest(out2) if (out2 / "run_manifest.json").is_file() else {}
    if code2 == 0:
        check("C", "C2 a path longer than 260 characters works",
              (out2 / "haplotypes.tsv").is_file(), f"len={len(str(out2))} exit=0")
    else:
        message = str(info2.get("error_message", "")) or "\n".join(lines2[-3:])
        check("C", "C2 a too-long path fails with an error naming the directory",
              ("outdir" in message.lower() or "directory" in message.lower()
               or "环境" in message or "Cannot" in message or "create" in message.lower()),
              f"len={len(str(out2))} exit={code2} class={info2.get('error_class')} "
              f"msg={message[:80]}")

    # C3: cache directory resolution order.
    import subprocess as sp
    rscript = runner.rscript
    script = work / "cache_dir.R"
    script.write_text(
        '.libPaths(c("D:/tools/R/lib", "C:/tools/R/lib"))\n'
        "suppressPackageStartupMessages(library(nanoamp))\n"
        "cat('cache:', nanoamp:::annotation_cache_dir(), '\\n')\n"
        "cat('client:', nanoamp:::annotation_http_client(), '\\n')\n",
        encoding="utf-8")
    cases = [
        ("NANOAMP_CACHE_DIR wins", {"NANOAMP_CACHE_DIR": str(work / "c_explicit")},
         str(work / "c_explicit")),
        ("LOCALAPPDATA is used when NANOAMP_CACHE_DIR is unset",
         {"NANOAMP_CACHE_DIR": None, "LOCALAPPDATA": str(work / "c_local"),
          "TEMP": str(work / "c_temp")},
         str(work / "c_local" / "nanoamp" / "cache" / "ref")),
        ("TEMP is the last resort",
         {"NANOAMP_CACHE_DIR": None, "LOCALAPPDATA": None, "TEMP": str(work / "c_temp2")},
         str(work / "c_temp2" / "nanoamp" / "ref")),
    ]
    probe_output = ""
    for label, env, expected in cases:
        with patched_env(**env):
            proc = sp.run([str(rscript), "--vanilla", str(script)],
                          capture_output=True, text=True, encoding="utf-8",
                          errors="replace", cwd=str(REPO), env=dict(os.environ))
        stdout = proc.stdout or ""
        probe_output = proc.stderr or probe_output
        got = ""
        for line in stdout.splitlines():
            if line.startswith("cache:"):
                got = line.split(":", 1)[1].strip()
        if got:
            same = (os.path.normcase(os.path.normpath(got)) ==
                    os.path.normcase(os.path.normpath(expected)))
            check("C", f"C3 cache dir: {label}", same, f"{got} (expected {expected})")
        else:
            check("C", f"C3 cache dir: {label}", False,
                  f"probe produced no output (exit={proc.returncode}) {probe_output[:120]}")

    # C5: the HTTP client. PATH cannot hide curl.exe on Windows (Sys.which also
    # searches the system directory), so the fallback is exercised directly:
    # the selection is asserted, and the R client is asked to fetch a real
    # Ensembl response.
    client_script = work / "client.R"
    client_script.write_text(
        '.libPaths(c("D:/tools/R/lib", "C:/tools/R/lib"))\n'
        "suppressPackageStartupMessages(library(nanoamp))\n"
        "cat('client:', nanoamp:::annotation_http_client(), '\\n')\n"
        "ok <- tryCatch({\n"
        "  txt <- nanoamp:::`.http_get_r`('https://rest.ensembl.org/info/software',\n"
        "                                list(`content-type` = 'application/json'))\n"
        "  grepl('release', txt)\n"
        "}, error = function(e) paste('ERROR:', conditionMessage(e)))\n"
        "cat('r-client-ok:', ok, '\\n')\n", encoding="utf-8")
    with patched_env(NANOAMP_NO_CACHE="1", HTTPS_PROXY=None, HTTP_PROXY=None):
        proc = sp.run([str(rscript), "--vanilla", str(client_script)],
                      capture_output=True, text=True, encoding="utf-8",
                      errors="replace", cwd=str(REPO), env=dict(os.environ))
    out5_text = proc.stdout or ""
    if "client: curl" in out5_text:
        check("C", "C5 the curl client is selected when curl.exe exists", True,
              "client=curl (a machine without curl.exe falls back to 'r')")
    else:
        check("C", "C5 the client selection reports a usable client",
              "client: r" in out5_text, out5_text.strip()[:80])
    check("C", "C5b R's own HTTP client can fetch from Ensembl (the no-curl fallback)",
          "r-client-ok: TRUE" in out5_text,
          next((ln for ln in out5_text.splitlines() if ln.startswith("r-client-ok")),
               (proc.stderr or "")[:80]))
    out5 = work / "c5"
    code5, lines5 = runner.run([
        "call", "--reads", str(fx["reads"]), "--reference", str(fx["ref"]),
        "--outdir", str(out5), "--mode", "A", "--aligner", "r",
        "--annotate-config", str(fx["cfg"]),
    ])
    rows5 = read_tsv(Path(out5) / "annotation.tsv")[1]
    check("C", "C5c the offline cds route needs no HTTP client at all",
          code5 == 0 and bool(rows5), f"exit={code5} rows={len(rows5)}")

    # C6: the R-native aligner (no external tool) and the pwalign provider.
    out6 = work / "c6"
    code6, lines6 = runner.run([
        "call", "--reads", str(fx["reads"]), "--reference", str(fx["ref"]),
        "--outdir", str(out6), "--mode", "A", "--aligner", "r",
    ])
    qc6 = read_qc(Path(out6))
    check("C", "C6 aligner=r works and records which provider supplied it",
          code6 == 0 and qc6.get("pairwise_provider", "") not in ("", "NA"),
          f"exit={code6} provider={qc6.get('pairwise_provider')}")

    # C8: no PATH help at all (an unmodified PATH on a machine that never
    # refreshed it): the offline route must still work.
    minimal_path = os.pathsep.join(
        p for p in os.environ.get("PATH", "").split(os.pathsep)
        if p and "nanoamp" not in p.lower())
    out8 = work / "c8"
    with patched_env(PATH=minimal_path, NANOAMP_MINIMAP2=None):
        code8, _ = runner.run([
            "call", "--reads", str(fx["reads"]), "--reference", str(fx["ref"]),
            "--outdir", str(out8), "--mode", "A", "--aligner", "r",
            "--annotate-config", str(fx["cfg"]),
        ])
    check("C", "C8 works without the install directory on PATH", code8 == 0,
          f"exit={code8}")

    # C7 / C10: already automated by the installer tests - run them here so the
    # stress report covers the installer side too.
    for name, case in (("test_r_version_choice.py", "C7 installer picks the right R"),
                       ("test_copy_retry.py", "C10 installer retries locked files"),
                       ("test_locked_file_retry.py", "C10b locked-file retry logic")):
        path = REPO / "release" / "_installer" / name
        if not path.is_file():
            record("C", case, "SKIP", f"{name} not found")
            continue
        proc = subprocess.run([sys.executable, str(path)], capture_output=True,
                              text=True, cwd=str(REPO))
        check("C", case, proc.returncode == 0,
              f"{name} exit={proc.returncode}")

    # C4 / C9 are not automatable on this machine.
    record("C", "C4 disk full", "SKIP",
           "needs a full volume: run `nanoamp call ...` with the output on a "
           "volume that has no free space and check the message names the disk")
    record("C", "C9 Windows ARM64 without a minimap2 binary", "SKIP",
           "needs ARM64 hardware: run with --aligner r and confirm annotation "
           "is unaffected")


# ---------------------------------------------------------------------------
# Group D: cancellation
# ---------------------------------------------------------------------------

def group_d(runner: NanoampRunner, work: Path) -> None:
    fx = make_offline_fixture(work / "d")
    # A long-ish run: many reads, one thread, so cancelling has something to
    # interrupt. Mode A with the R aligner is the slowest path we control.
    big_reads = work / "d_reads.fastq"
    ref = fx["ref"].read_text(encoding="utf-8").splitlines()[1]
    with big_reads.open("w", encoding="utf-8") as fh:
        for i in range(4000):
            fh.write(f"@d{i}\n{ref}\n+\n{'I' * len(ref)}\n")
    out = work / "d1"

    import subprocess as sp
    wrapper = runner.write_wrapper()
    cmd = [str(runner.rscript), "--vanilla", str(wrapper),
           "call", "--reads", str(big_reads), "--reference", str(fx["ref"]),
           "--outdir", str(out), "--mode", "A", "--aligner", "r", "--threads", "1"]
    proc = sp.Popen(cmd, cwd=str(REPO), stdout=sp.PIPE, stderr=sp.STDOUT,
                    env=dict(os.environ) | {"R_LIBS_USER": "D:/tools/R/lib",
                                            "PYTHONUTF8": "1"})
    time.sleep(6)
    cancelled = proc.poll() is None
    if cancelled:
        proc.kill()
    proc.wait(timeout=60)
    info = read_manifest(out)
    check("D", "D1 cancelling kills the run and keeps the partial output",
          cancelled and Path(out).is_dir(),
          f"killed_mid_run={cancelled} exit={proc.returncode} outdir_exists={Path(out).is_dir()}")
    check("D", "D1b a cancelled run does not claim to be done",
          info.get("status") != "done",
          f"status={info.get('status', '(no manifest)')}")
    leftovers = sorted(p.name for p in Path(out).glob("*")) if Path(out).is_dir() else []
    record("D", "D1c partial files are preserved (nothing deleted)",
           "PASS" if Path(out).is_dir() else "FAIL",
           f"{len(leftovers)} entries remain: {leftovers[:6]}")

    # D2: cancelling during the annotation phase. A haploype-rich fixture is
    # used so the annotation step takes long enough to be interrupted.
    out2 = work / "d2"
    big = make_big_haplotype_fixture(work / "d2_fixture")
    cmd2 = [str(runner.rscript), "--vanilla", str(wrapper),
            "call", "--reads", str(big["reads"]), "--reference", str(big["ref"]),
            "--outdir", str(out2), "--mode", "A", "--aligner", "r",
            "--annotate-config", str(big["cfg"]), "--annotation-detail",
            "--min-reads", "3", "--min-freq", "0.01"]
    proc2 = sp.Popen(cmd2, cwd=str(REPO), stdout=sp.PIPE, stderr=sp.STDOUT,
                     env=dict(os.environ) | {"R_LIBS_USER": "D:/tools/R/lib",
                                             "PYTHONUTF8": "1"})
    # Kill as soon as the haplotype table exists: that is "during annotation".
    deadline = time.time() + 30
    while time.time() < deadline and not (Path(out2) / "haplotypes.tsv").is_file():
        if proc2.poll() is not None:
            break
        time.sleep(0.05)
    during_annotation = proc2.poll() is None
    if during_annotation:
        proc2.kill()
    proc2.wait(timeout=60)
    ann = Path(out2) / "annotation.tsv"
    readable = True
    if ann.is_file():
        f, r = read_tsv(ann)
        readable = bool(f) and all(len(row) >= len(f) - 1 for row in r)
    check("D", "D2 a kill during annotation leaves no unreadable annotation.tsv",
          readable, f"killed_during_annotation={during_annotation} "
                    f"annotation.tsv={'present' if ann.is_file() else 'absent'}")


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--group", default="A,B,C,D")
    ap.add_argument("--outdir", default="tmp/test_results/stress")
    ap.add_argument("--keep", action="store_true",
                    help="keep the scratch directory (default: keep on failure)")
    args = ap.parse_args()

    groups = [g.strip().upper() for g in args.group.split(",") if g.strip()]
    out_root = (REPO / args.outdir).resolve()
    out_root.mkdir(parents=True, exist_ok=True)
    work = Path(tempfile.mkdtemp(prefix="nanoamp_stress_", dir=str(out_root)))
    print(f"scratch   : {work}")
    try:
        runner = NanoampRunner(REPO)
        print(f"rscript   : {runner.rscript}")
        print(f"groups    : {', '.join(groups)}\n")
        for group in groups:
            print(f"=== group {group} ===")
            fn = {"A": group_a, "B": group_b, "C": group_c, "D": group_d}.get(group)
            if fn is None:
                record(group, "unknown group", "SKIP", "known groups: A, B, C, D")
                continue
            try:
                fn(runner, work)
            except Exception as exc:  # noqa: BLE001 - a crashed case is a failure
                import traceback
                traceback.print_exc()
                record(group, "group crashed", "FAIL", f"{type(exc).__name__}: {exc}")
            print()
    finally:
        results_path = out_root / "stress_results.tsv"
        with results_path.open("w", encoding="utf-8") as fh:
            fh.write("group\tcase\tstatus\tdetail\n")
            for row in RESULTS:
                fh.write(f"{row['group']}\t{row['case']}\t{row['status']}\t{row['detail']}\n")
        passed = sum(1 for r in RESULTS if r["status"] == "PASS")
        failed = [r for r in RESULTS if r["status"] == "FAIL"]
        skipped = sum(1 for r in RESULTS if r["status"] == "SKIP")
        print(f"PASS {passed}  FAIL {len(failed)}  SKIP {skipped}")
        print(f"results: {results_path}")
        if failed:
            print("\nfailed cases:")
            for row in failed:
                print(f"  - [{row['group']}] {row['case']}: {row['detail']}")
        if not args.keep and not failed:
            shutil.rmtree(work, ignore_errors=True)
        else:
            print(f"scratch kept: {work}")
    return 1 if any(r["status"] == "FAIL" for r in RESULTS) else 0


if __name__ == "__main__":
    raise SystemExit(main())
