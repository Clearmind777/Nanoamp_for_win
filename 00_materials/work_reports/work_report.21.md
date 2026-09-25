# 工作报告 21：同步 Linux 领先功能（第二批）——契约文档、结构化状态、去 ShortRead、功能回归与压力矩阵

- 日期：2026-09-26
- 仓库：`Nanoamp_for_win`（Windows 专用）
- 上一轮：`work_report.20.md`（注释子系统与 GUI 组件，提交 `49c1c80`）
- 本轮委托：「请实施方案，待各种验证顺利完成后，比较 linux 和 win 两版本的测试结果一致性，然后酌情提交与推送。」
- 方案依据：`E:\bioinfo\resource\repo\gitshortage\tmp\nanoamp-win-vs-linux-and-plan.md`（GUI 优先版 v3）

---

## 1. 本轮做了什么（对照方案编号）

| 方案编号 | 事项 | 状态 |
|---|---|---|
| **P0-6** | 契约与文档：`output_schema.md` 注释/`status` 章节、tutorial 注释章节（§0.7、§1.2 第 5 步、§2.10）、`release/*` 四份 README | ✅ 完成 |
| **P0-7** | `run_manifest.json` 的 `status` / `error_class` / `error_message` / `log_path` + `nanoamp.log` + GUI 按类给提示 + 可选 `--strict` | ✅ 完成 |
| **P1-2** | GUI 转录本选择：「列出转录本」按钮 + `transcripts.tsv` + 「转录本」下拉框（`--transcript <ENST>`） | ✅ 完成 |
| **P1-3** | 去 `ShortRead`：自带 FASTQ 解析器（gzip 按魔数识别、畸形拒绝、id 去 `@`、序列大写化） | ✅ 完成 |
| **P1-4** | GUI 缓存/网络面板：`doctor` 增列内容已足够 + 「复制诊断信息」按钮（缓存目录/清缓存已在 CLI 与 doctor 覆盖） | 🟡 部分（清缓存按钮未加） |
| **P1-5** | 功能回归接线：`make functional-test` + 提交基线 + `check_functional_baseline.R` | ✅ 完成 |
| **§6 压力矩阵** | `03_dependence/stress/run_stress_tests.py`（A–D 组 47 个可自动化用例全绿，2 个需真机的 SKIP 并写清手工步骤） | ✅ 完成（可自动化部分） |

本轮额外发现并修掉的上游缺陷：**L11**（Mode B 不可复现）、**L12**（大响应体被 R 的管道捕获截断）、缓存自愈、输入类错误分类。

---

## 2. P0-7：结构化状态与错误分类

`run_manifest.json` 现在同时回答"跑完了吗""哪一类问题""日志在哪"：

| 字段 | 取值 | 谁写 |
|---|---|---|
| `status` | `done` / `failed` / `cancelled` | R（`done`/`failed`）、GUI（`cancelled`，因为 R 进程已被杀） |
| `error_class` | `input` / `environment` / `network` / `internal` | R，仅在 `failed` 时 |
| `error_message` | 可操作的原文 | R |
| `log_path` | `<outdir>\nanoamp.log` | R（该文件同时含终端里的全部日志） |

- 失败运行**也会创建输出目录**并写下 manifest + 日志，所以"失败后什么都没有"不会发生；
- 新增 `nanoamp_abort(message, class=)` 与 `error_class_of()`：显式分类优先，其次按错误文本归类；
- 空 FASTQ、无 reads 比对成功、过滤后无 reads 现在都归为 `input`（此前是 `internal`），且文案指名文件；
- GUI 按 `error_class` 给出四套"怎么办"提示（`network` → 建议改用离线 CDS 配置），取消运行会把 manifest 标成 `cancelled`；
- 可选 `--strict`：注释有转录本被跳过时 `status=failed` 且退出码 1（**不引入第三种退出码**，与 §7 契约的 0/1 保持一致；这一决定已写回方案文件）。

## 3. P1-3：去 ShortRead（自带 FASTQ 解析器）

- `R/io.R`：新增 `fastq_connection()`（按扩展名**或 gzip 魔数**识别压缩）、`read_fastq_records()`（四行一记录，块读）、`read_fastq()`（id 去 `@`、序列大写化）、`count_fastq_reads()`（流式计数，不建表）；
- 畸形输入**明确报错**而不是猜：行数不是 4 的倍数、缺 `@` 头、缺 `+` 分隔符三种都被拒绝；
- `DESCRIPTION` 去掉 `ShortRead` 依赖；`inst/windows/build_installer.R`、`inst/scripts/run_functional_tests.R`、安装器的 `need`/自检清单、`README{,-CN}.md`、`inst/docs/INSTALL_DEPENDENCIES{,-CN}.md`、`03_dependence/r-environment/README.md` 同步更新；
- 安装器的**固定版本清单保持超集**（仍列 ShortRead）：离线包资产已冻结校验，删包需要重新生成并重验整个离线包，收益不足；
- 新测试 `test-io-fastq.R`（7 个用例：正常/gzip 双通道/三种畸形/空文件/分块读取/缺失文件/依赖断言）；
- 端到端回归：168 个真实运行的结果与旧（ShortRead）实现**逐行一致**（见 §6）。

## 4. P1-2 / P1-4：GUI 转录本选择与诊断

- 「列出转录本」按钮：跑一次 `call ... --list-transcripts`（需要 Reads/目的序列/配置），把 `transcripts.tsv` 读成下拉框选项，日志里打印每个转录本的 `name/biotype/MANE/canonical`；离线 CDS 路线下该控件禁用并把选择重置为「自动选择」；
- 选中的 ENST 以 `--transcript <id>` 传给 CLI（默认「自动选择（MANE / 规范）」**不传**该参数）；
- 「复制诊断信息」按钮：把运行日志（含 `doctor` 全部输出）连同仓库根与 Rscript 路径复制到剪贴板；
- 容错（E4/E6）：`annotation.tsv` 畸形/不可读/重复行/短行时**不崩**，状态栏说明"不符合契约"；QC 与日志同样容错；中文与超长日志行不丢字。

## 5. L11 / L12：两个上游级缺陷（实测确证）

| 编号 | 缺陷 | 证据 | 修法 |
|---|---|---|---|
| L11 | `DECIPHER::Clusterize` 未固定随机种子 → **Mode B 结果不可复现** | 同一批 reads、同一 R 会话、`processors = 1`：38/38/35 簇；用包路径连续 5 次 Mode B 的 top1 = 0.2817/0.3122/0.4038/0.2770/0.2887；`cutoff = 0.02` 探针 30/29/29/29 | `with_cluster_seed()`（默认 42）包裹 `Clusterize`/`AlignSeqs`，保存并恢复调用方 `.Random.seed`，种子写入 `qc.tsv: clustering_seed` |
| L12 | `system2(..., stdout = TRUE)` 会**给超长行插入换行** → 大的单行响应被破坏 | 39,893 字符的 Ensembl JSON 变回 39,897 字符/5 行，`GRCh38` 被切成 `GR Ch38`、`havana_tagene` 被切开；`--transcript all` 因此直接失败 | HTTP 客户端改为 `curl -o <临时文件>` 再读文件；新增 `test-http-client.R`（用 `file://` URL，不需要联网） |

另外两处稳健性修复：JSON/HTTP 缓存项读不出来时**自动丢弃并重取**（不再让一次半截写入毒化后续所有运行）；`--transcript all` 里单个转录本取不到权威 CDS 时**按"部分完成"记账**（5 成功 / 1 跳过，原因可查），而不是整跑失败。

## 6. 验证证据

| 验证 | 结果 |
|---|---|
| `R CMD check`（`R_LIBS_USER=D:\tools\R\lib`） | **Status: OK** |
| testthat | **42 个用例 / 158 个断言全通过**（新增 `test-io-fastq.R` 7 例、`test-http-client.R` 3 例、`test-cli-flags.R` 增加 P0-7 与 `--strict`） |
| GUI 自测（7 个脚本） | 全部 exit 0（新增 `test_failure_reporting.py`；`test_annotation_gui.py` 增加转录本选择/容错/日志检查） |
| 安装器逻辑（9 个脚本） | 全部 exit 0 |
| 功能回归（168 个真实运行） | `make functional-test` → **FUNCTIONAL BASELINE MATCHED**；再跑一遍仍逐行相同（Mode B 也一致） |
| 压力矩阵 A–D | **47 PASS / 0 FAIL / 2 SKIP**（SKIP 为磁盘满、ARM64，均写明手工步骤；`tmp/test_results/stress/stress_results.tsv`） |
| 跨版本一致性 | `tmp/xver2_compare.R` → **CROSS-VERSION COMPARISON OK**（见 §7） |
| 离线安装 + 安装树 CLI 注释端到端 | `install exit=0`；`<安装目录>\configs\` 有示例配置；安装树 CLI 跑 E4-3 离线 CDS 注释得到 **12 行 annotation / 22 行变异明细**，`status=done`、`protein_verified=false`、`nanoamp.log` 存在（见 §8） |
| 冻结 GUI exe 字符串检查 | 12 个关键字符串全部存在（注释面板、转录本选择、复制诊断、失败提示等） |

## 7. Linux 与 Windows 测试结果一致性（本轮重点）

用同一份数据（`01_data/TSM20260826/E4-3`）、同一 `aligner = "r"`（排除平台二进制差异）、
对两端各跑两遍，逐列比较（脚本：`tmp/xver2_run.R` + `tmp/xver2_compare.R`）：

| 项目 | 结果 |
|---|---|
| Mode A `haplotypes.tsv` | 4 × 13，**每个共有列完全一致** |
| Mode A `variants.tsv` | 515 × 12，**完全一致** |
| Mode A `qc.tsv` | 17 个共有指标**完全一致**；Windows 未新增指标 |
| Mode C `haplotypes.tsv` | 290 × 9，**完全一致** |
| `annotation.tsv`（离线 cds 路线，同一配置） | 行数、count、proportion、CDS、蛋白长度、变异一列不差；**唯一差异**是"与目的序列完全一致"那一行的后果标签：Linux `synonymous` → Windows `no_variant`（L4 修复），其余行的 `consequence_en`/`consequence_zh`/`protein_change` 全部相同 |
| Mode B | Windows 两遍**完全一致**；Linux 两遍"碰巧一致"，但同一输入的未固定种子调用实测会出现 38/38/35 与 30/29/29/29 的差别（脚本会现场复测并打印） |
| `run_manifest.json` | Windows 新增 `status=done`、`log_path`（+ `nanoamp.log`）；`protein_verified`：Linux 对离线 cds 路线谎报 `true` → Windows 如实 `false`（L10） |

结论：**数值结果一致**；差异只有三类，且全部是 Windows 侧有意修复的、可逐条解释的行为
（L4 标签、L10 字段、L11 种子），没有"说不清的差异"。

## 8. 发行工程

- `release/01_R-package/nanoamp_0.1.0.tar.gz`（88,701 B）、`release/03_GUI/nanoamp.exe`（11,298,617 B）、
  `release/install.exe`（11,920,619 B）/`uninstall.exe`（11,268,594 B）重建；
- 安装器新增一步：把随包示例配置复制到 `<安装目录>\configs\`（实测 `install exit=0` 后该目录含
  `example_cds.json` / `example_online.json` / `README.md`），自检增加 `curl` 与 `configs` 两行；
- `python release/_build/build_assets.py` 重打两个资产并刷新 `release/_build/SHA256SUMS.txt`
  （setup `e5696169…`，offline-deps 未变 `2db72289…`；zip 本身不入库）；
- 顺带修掉随包 `example_cds.json` 里指向已废弃的 `01_data/test_data/...` 的说明性字段，
  改成规范化的 `01_data/TSM20260826/E4-3/reference.self.fa`；
- 复验：离线沙箱安装 + 安装树 CLI 注释端到端 12 行 / 22 行（见 §6 表）；冻结 exe 字符串检查全绿。

## 9. 仍未做（诚实清单）

1. GUI 高级参数面板（`aligner` / `threads` / `min_*`）与「清空缓存」按钮未做（P1-4 部分）；
2. 未做上游回灌（Linux 仓库 L1–L12 + Windows 的 batch 空目录清理），按要求不擅自改另一个仓库；
3. 压力矩阵中 C4（磁盘满）、C9（ARM64）、E2（高 DPI）仍需真机手工验证；
4. 在线路线在**本仓库自带数据集**上仍未跑通（E4-3 不在内置 panel）：本轮用真实 GRCh38 片段
   证明了在线路线本身可用，E4-3 的场景仍作为已知限制记录；
5. 未发布任何 GitHub Release（按要求只提交与推送）。
