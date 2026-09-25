# 工作报告 20：同步 Linux 领先功能（第一批）——核心修复 + 功能注释 + GUI 组件

- 日期：2026-09-26
- 仓库：`Nanoamp_for_win`（Windows 专用）
- 上一轮：`work_report.19.md`（安装器复制重试）
- 本轮委托：「请实施方案，待各种验证顺利完成后，比较 linux 和 win 两版本的测试结果一致性，然后酌情提交与推送。」
- 方案依据：`E:\bioinfo\resource\repo\gitshortage\tmp\nanoamp-win-vs-linux-and-plan.md`（GUI 优先版 v3）

---

## 1. 本轮做了什么（对照方案编号）

| 方案编号 | 事项 | 状态 |
|---|---|---|
| **P0-1** | 三项高严重度核心修复（`write_tsv` 消毒、pairwise provider 懒解析、DECIPHER 警告折叠） | ✅ 完成并验证 |
| **P0-2** | 注释配置层 + 示例配置随包（修上游 L2 硬编码 pwalign、L8 `configs/` 不进包） | ✅ 完成 |
| **P0-3** | 注释核心（离线 `cds` 路线打通；修 L4 无变异标签、L6 负链等位基因反向互补） | ✅ 完成 |
| **P0-4** | CLI 8 个注释/缓存开关 + `doctor` 注释前置检查 | ✅ 完成 |
| **P0-5** | GUI：注释面板 + CDS 表单 + 注释结果/变异注释标签页 + 三态状态条 + 窗口自适应 | ✅ 完成 |
| **P0-6** | 契约与文档（`output_schema` 注释章节、tutorial 注释章节） | ⏳ **未完成**（README 已更新限制与用法） |
| **P0-7** | `run_manifest.json` 的 `status`/`error_class` 结构化错误分类 | ⏳ **未完成** |
| **P1-*** | 在线路线完整验证、去 ShortRead、功能回归接线、GUI 转录本选择/缓存面板、压力矩阵 | ⏳ 下一轮 |

---

## 2. P0-1：三项核心修复（上游已验证、Windows 侧此前缺失）

| 修复 | 文件 | 证据 |
|---|---|---|
| `write_tsv` 字段消毒（换行/制表符 → 空格） | `R/utils.R` | `tmp/verify_p01.R`：含 `\n`/`\t` 的字段不再拆行，`fread` 读回完整 3 行 |
| pairwise provider 改为**懒解析 + 优先 pwalign + `getExportedValue` 判定 + 删除 `.onLoad` 急切解析** | `R/zzz.R` | 调用前 `pa_provider_name()` 返回 `NA`（不再在 `library()` 阶段解析）；首次成对比对后解析为 `pwalign` |
| DECIPHER 警告折叠为单行 `distance_note`，并写入 qc（`clustering_note`/`pairwise_provider`） | `R/cluster.R`、`R/correct.R` | Mode B 端到端 **0 条 R 警告外泄**；`qc.tsv` 出现 `clustering_note = "16 different sequence lengths. Using shorter length in each comparison."` 与 `pairwise_provider = pwalign` |

> 意义：`library(nanoamp)` 不再因缺少 provider 而失败；批量 Mode B 不再刷 "50 or more warnings"；
> `qc.tsv` 里的换行不会再让 `fread` 静默截断（GUI 的 QC/注释表因此能整行显示）。

---

## 3. P0-2/P0-3：功能注释子系统（移植 + 批判性修正）

### 3.1 移植内容

- 新增 `R/annotate.R`（1125 行）、`R/annotate_config.R`（511 行）、`R/ref_online.R`（458 行）——整份移植；
- 新增 `inst/configs/{example_cds.json,example_online.json,README.md}`：**放进包内**，从而修掉上游 L8
  （上游 `.Rbuildignore` 把 `configs/` 排除出 tarball，导致安装版拿不到示例配置、测试被 skip 1 条）；
  实测新 tarball 内已含 `nanoamp/inst/configs/`；
- 四个注释参数（`annotation` / `list_transcripts` / `annotation_proteins` / `annotation_detail`）
  按上游方式接入 `haplotypes.R` → `correct.R` / `cluster.R` / `exact.R`；
- `zzz.R` 的 `globalVariables` 合并上游新增的 18 个注释相关变量名。

### 3.2 平台适配（Windows）

| 适配点 | 做法 | 证据 |
|---|---|---|
| 缓存目录 | `NANOAMP_CACHE_DIR` → `%LOCALAPPDATA%\nanoamp\cache\ref` → `%TEMP%\nanoamp\ref`（不再落到 `Documents\.cache`） | `nanoamp doctor` 显示 `cache-dir ...\localappdata/nanoamp/cache/ref` |
| `curl` 依赖 | 保留 `curl` 优先，新增 R 内回退 `.http_get_r()`（`download.file`），缺失时不再直接失败；`doctor` 显式显示 curl 状态 | `doctor`：`curl C:\Windows\SYSTEM32\curl.exe` |
| `--no-cache` 语义（上游 L1） | 改为**绕过缓存**（`NANOAMP_NO_CACHE=1`），**不再删除**整个缓存目录 | 新测试 `--no-cache bypasses the cache instead of deleting it` |
| 硬编码 pwalign（上游 L2） | `annotate_config.R` 的 `.pa()` 改走 `zzz.R` 的 provider 抽象（`.pa_fn`） | 与 `zzz.R` 同口径；`R CMD check` OK |

### 3.3 修掉的两个语义缺陷（带判别性证据）

- **L4 无变异单倍型**：原来（上游现状）参考序列本身被标成 `synonymous`，读起来像"有编码改变但沉默"。
  现在标 `no_variant`（词表里本来就有这一项，只是从未产生）。E4-3 实测：H2 → `无变异` / `p.(=)`。
- **L6 `cds` 路线 + 负链**：原来只把位置镜像，**没有对等位基因取反向互补**，于是负链上的替换被拿去和
  错误的参考碱基比较，后果几乎必然是 `synonymous`。现在按链取反向互补（抽出 `.annotation_rc_alleles()`
  供基因组路线与 cds 路线共用）。

  判别性验证（`tmp/verify_l6.R`，合成参考、不经比对以保证确定性）：

  ```text
  plus  (R,  cds +) : no_variant, missense p.Ile4Asn, missense p.Tyr21Asn, frameshift p.Cys8fs
  minus (rc(R), -)  : no_variant, missense p.Ile4Asn, missense p.Tyr21Asn, frameshift p.Cys8fs   ← 一致
  反向对照（把 rc 换回恒等）：synonymous, synonymous, frameshift                                ← 正是上游的错
  ```

---

## 4. P0-4：CLI 与 doctor

- `cli_call_options()` / `cli_batch_options()` 各新增 8 个开关：`--annotate-config`、`--transcript`、
  `--list-transcripts`、`--clear-cache`、`--no-cache`、`--cache-dir`、`--annotation-proteins`、
  `--annotation-detail`；
- 移植上游的**长选项缩写拒绝**（`cli_check_flags` / `cli_long_flags` / `cli_legacy_flag_hint`）：
  `--annotate` 会报错并提示 `--annotate-config`，`--ensembl-release` 会提示读 `run_manifest.json`；
- `usage` 增加注释参数与示例；
- `doctor` 增加：`curl` 状态、缓存目录与体积、随包 `configs/` 路径、注释可用性结论；
- **batch 现在真的转发注释参数**（上游虽接受这些开关却从不转发，`batch --annotate-config` 静默无效——已在注释里写明）。

---

## 5. P0-5：GUI 组件（本轮重点）

| 组件 | 实现 |
|---|---|
| 启用开关 | 放在输入区（模式 / 显示前 n 条 / **功能注释…**），关闭时明细区**整块隐藏、不占高度** |
| 配置来源 | 下拉：**离线 CDS（不联网）** / 在线 genome（需联网，用 Ensembl）/ 自定义 JSON…（文件选择） |
| CDS 表单 | 起 / 止 / 链 / 读码框；实时提示 CDS 长度与密码子数；**长度不是 3 的倍数时直接拒绝开跑**并说明要删几 bp |
| 注释结果标签页 | `annotation.tsv`：编号 / 转录本 / 后果 / 最严重后果 / 转录本冲突 / 蛋白变化 / 变异；选中行会联动「单倍型结果」 |
| 变异注释标签页 | `variants_annotation.tsv`（勾选变异级明细时）：参考坐标 / CDS 坐标 / 密码子 / 氨基酸 / 后果 |
| 三态状态条 | 已注释 N 个转录本、M 个单倍型 / 部分完成（跳过 K 个 + 原因）/ 注释不可用（原因）——**明确不用"annotation.tsv 有几行"判断覆盖** |
| Mode C 保护 | 模式 C 下勾选注释会被明确告知"模式 C 不执行注释"，参数不传下去（与 R 侧行为一致） |
| 窗口自适应 | 启用注释时窗口按需增高（不超过屏幕），关闭时恢复；短屏（864 px）下笔记本自动收缩，实测注释表仍有 293 px |
| 在线路线提示 | 明确写出"需要联网"与"不在内置 panel 时会退化为逐染色体扫描，可能非常慢" |

---

## 6. 验证结果（本轮的证据链）

| 验证 | 结果 |
|---|---|
| `R CMD check --no-manual --no-build-vignettes` | **Status: OK** |
| testthat（`03_dependence/r-environment/run_tests.R`） | **5 个文件 / 26 用例 / 86 断言，全部通过**（原 12 用例 / 38 断言） |
| 安装器测试（9 个脚本） | 全部 exit=0 |
| GUI 测试（6 个脚本，含新增 `test_annotation_gui.py`） | 全部 exit=0 |
| 离线安装（最终资产，含 `_offline`） | `install exit=0`；`doctor` 显示 curl / 缓存目录 / `configs/` / 注释可用 |
| **安装树 GUI 注释端到端** | 12 行注释（移码/无变异/同义…）、22 行变异级明细、状态条"已注释 1 个转录本、12 个单倍型（来源：cds-config）" |
| frozen `nanoamp.exe` | 启动正常；用 PyInstaller 归档读取（PYZ 代码常量）确认**已包含注释面板**（离线 CDS / variants_annotation.tsv / --annotate-config 等字符串均在） |
| 在线路线实测 | Ensembl REST 可达（**release 116**，与 Linux 基线一致）；ZNF8 样本经内置 panel 定位到 `19:58285652-58285962(+)`；因参考与基因组仅匹配 42%，**V3 锚定安全检查按设计拒绝**并给出可操作建议 |
| 在线路线的已知慢路径 | 不在 panel 的扩增子（E4-3）退化为逐染色体扫描：实测 chr21 从 10% 到 21% 约 2.5 分钟 → 已在 GUI 提示与 README 限制里写明 |

### 6.1 两版本测试结果一致性（委托方点名）

同一输入（`01_data/TSM20260826/E4-3` 的同一批文件）、同一 `aligner = "r"`（纯 R 代码，排除平台二进制差异），
分别安装 **Linux 版**（`tmp/linux_lib`）与 **Windows 版**（`D:/tools/R/lib`）后对比（`tmp/xver_compare.R`）：

| 对比项 | 结果 |
|---|---|
| Mode A：`haplotypes.tsv` | 4 × 13 完全相同（逐列逐行） |
| Mode A：`variants.tsv` | 515 × 12 完全相同 |
| Mode A：`qc.tsv` | 17 个共有指标**全部相同**；无一方独有指标 |
| Mode B：`haplotypes.tsv` / `variants.tsv` | 28 × 13 / 11 × 7 完全相同 |
| Mode B：`qc.tsv` | 共有指标相同；`clustering_note` 文本一致；`pairwise_provider` 双方均为 `pwalign` |
| Mode C：`haplotypes.tsv` | 290 行完全相同 |
| 注释（cds 路线，同一配置文件） | 行数与所有非后果列相同；**唯一差异是刻意的 L4 修复**：参考型 `synonymous` → `no_variant`；带变异的行后果与蛋白变化完全一致 |

**结论：两个版本的核心分析结果逐列一致；注释侧的唯一差异是本轮有意修掉的上游缺陷。**
（另有 4 处 Windows 独有/上游独有的行为差异已在方案 §3.7 记录：`shQuote` 空格路径修复、batch 空目录清理、
`--no-cache` 语义、`no_variant` 标签。）

---

## 7. 本轮改动的文件

**R 包**：`R/annotate.R`（新）、`R/annotate_config.R`（新）、`R/ref_online.R`（新）、`R/zzz.R`、`R/utils.R`、
`R/cluster.R`、`R/correct.R`、`R/exact.R`、`R/haplotypes.R`、`R/cli.R`、`inst/configs/*`（新）、
`tests/testthat/test-annotate-offline.R`（新）、`tests/testthat/test-cli-flags.R`（新）、
`man/run_haplotype_analysis.Rd`。

**GUI**：`02_code/PythonGUI/nanoamp_gui/app.py`、`tests/test_annotation_gui.py`（新）、
`release/03_GUI/nanoamp.exe`（重新构建）、`02_code/PythonGUI/dist/nanoamp.exe`。

**工程**：`Makefile`（`gui-test` 纳入注释面板测试）、`README.md`（新增"功能注释（可选）"章节、
改写已知限制）、`release/01_R-package/nanoamp_0.1.0.tar.gz`（42,185 → 79,561 B）、
`release/_build/SHA256SUMS.txt`（setup `2a822d08…`，离线依赖包未变 `2db72289…`）。

---

## 8. 复现命令

```powershell
# R 侧
Rscript 03_dependence/r-environment/run_tests.R          # 26 用例 / 86 断言
R CMD build 02_code/r --no-build-vignettes
R CMD check --no-manual --no-build-vignettes nanoamp_0.1.0.tar.gz   # Status: OK

# 离线注释 + 负链镜像（确定性，Tk 无关）
Rscript tmp/verify_annot_cds.R     # 真实样本 12 条单倍型
Rscript tmp/verify_l6.R            # 正负链一致 + 反向对照

# 两版本一致性
Rscript tmp/xver_run.R <lib> tmp/xver/<tag> <tag>        # linux_lib / D:/tools/R/lib
Rscript tmp/xver_compare.R

# GUI
python 02_code/PythonGUI/tests/test_annotation_gui.py
python tmp/gui_check_annot_installed.py                  # 需要 NANOAMP_HOME 指向安装树

# 资产
python release/_build/build_assets.py
```

---

## 9. 遗留（下一轮，按方案优先级）

1. **P0-6 文档**：`shared/docs/output_schema.md` 的注释四节、`00_materials/tutorial.md` 的注释章节、
   `release/README.md` 与各交付 README 的同步；
2. **P0-7**：`run_manifest.json` 的 `status` / `error_class`（GUI 需要按"输入/环境/网络"给不同提示）；
3. **P1**：`io.R` 去 `ShortRead`（P1-3）、功能回归接线 `make functional-test`（P1-5，脚本已在仓库）、
   GUI 转录本选择器与缓存面板（P1-2/P1-4）、在线路线在"参考与基因组匹配良好"的样本上的完整成功验证；
4. **压力矩阵**：`tmp/nanoamp-win-vs-linux-and-plan.md` §6 的 A–F 逐条执行并固化为 `make stress-test`
   （本轮已覆盖：断网 cds 成功、curl 缺失回退（代码路径）、大注释矩阵（12 × 1）、取消、窗口自适应、
   离线/联网安装分支）；
5. **上游回灌**：L1/L2/L4/L6/L8 已在本轮修掉，建议回灌 Linux 仓库；Windows 独有的 batch 空目录清理亦应同步。
