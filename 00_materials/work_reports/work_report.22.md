# 工作报告 22：第三批——GUI 高级参数/缓存网络/蛋白视图与联动，并修掉 R 比对后端的假覆盖度

- 日期：2026-09-26
- 仓库：`Nanoamp_for_win`（Windows 专用）
- 上一轮：`work_report.21.md`（契约文档、结构化状态、去 ShortRead、功能回归与压力矩阵，提交 `406b87e`/`85a5377`）
- 本轮委托：「请实施方案，待各种验证顺利完成后，比较 linux 和 win 两版本的测试结果一致性，然后酌情提交与推送。」
- 方案依据：`E:\bioinfo\resource\repo\gitshortage\tmp\nanoamp-win-vs-linux-and-plan.md`（GUI 优先版 v3）

---

## 1. 本轮做了什么

| 方案编号 | 事项 | 状态 |
|---|---|---|
| **P1-4 / G10** | GUI **高级参数面板**：比对方式（minimap2 / r）、线程、最小支持 reads、最小频率、最小一致度、最小覆盖、聚类一致度、最小簇 reads、簇共识、是否保留 BAM；**只发送改动过的参数**，可一键恢复默认 | ✅ 完成 |
| **P1-4 / G7** | GUI **缓存/网络面板**：缓存目录/文件数/占用、刷新、清空缓存、「测试 Ensembl 连接」 | ✅ 完成 |
| **P1-4 / G9** | GUI **蛋白序列视图**：可滚动、可复制的独立窗口（长蛋白不挤占结果表） | ✅ 完成 |
| **P1-5 / E7** | **单倍型 ↔ 注释联动**：选中单倍型后注释/变异两页自动筛选，可「显示全部」 | ✅ 完成 |
| 补充 | CLI：`nanoamp cache [--clear]`、`nanoamp doctor --check-online`、`--min-ref-coverage`；`--clear-cache` 可单独使用 | ✅ 完成 |
| 缺陷 | **L13：R 内比对后端的覆盖度是假的**（详见 §3） | ✅ 修复并验证 |

同时修掉两个界面缺陷：动作按钮曾在同一列重叠（新增按钮没挪位置）；隐藏可选面板后
窗口会留下约 320 px 空白（Tk 的 `grid_remove` 不收缩 *容器* 行——改为每个面板各占一行）。

## 2. 高级参数面板：默认值即 R 层默认值

面板勾选后才出现，字段初值取自 R 层默认（`R/defaults.R`）。`_advanced_args()` 只把
**与默认不同**的值转成命令行参数，因此"勾上但不动"与"不勾"完全等价（有测试断言
未改动时参数列表为空）。校验在起跑前完成：非数字、频率/一致度不在 0–1、线程不在
1–256 都会弹窗说明而不是带坏参数起跑。

实测（`test_annotation_gui.py` §6g）：把线程改 8、最小支持 reads 改 4、最小频率改 0.05、
最小覆盖改 0.8、聚类一致度改 0.98、最小簇 reads 改 5 时，参数恰好是

```text
--threads 8 --min-reads 4 --min-freq 0.05 --min-ref-coverage 0.8 --identity-cutoff 0.98 --min-cluster-reads 5
```

选择 `r` 时加 `--aligner r`；取消"保留 BAM"时加 `--no-intermediates`；簇共识改 medoid
时加 `--consensus-method medoid`。

## 3. L13：R 内比对后端把"部分覆盖"当成"全覆盖"（本轮最重要的发现）

`align_reads_r()` 对每条 read 都硬编码：

```r
ref_span = ref$length      # 参考序列全长
identity = 1 - nm / ref$length
ref_end  = ref$length
ref_cov  = 1               # 覆盖度恒为 1
```

后果（实测）：

| 现象 | 证据 |
|---|---|
| 只覆盖一半扩增子的 read 也能通过 `--min-ref-coverage 0.99` | 160 bp 参考 + 80 bp read：`ref_span=160`、`identity=1`、`ref_cov=1`，5 条全部进入统计 |
| 这类 read 被当成**参考单倍型**计数 | 同一探针：`n_reads_used=5`，`top1_is_reference=TRUE` |
| `qc.tsv` 的 `mean_coverage` 恰好等于 reads 条数 | E4-3（438 reads / 529 bp）：Linux `mean_coverage = 415.0000`，而 Windows 修复后为 `414.8412`（= 真实覆盖片段之和 ÷ 参考长度） |
| 参考末端的深度被高估 | E4-3 `variants.tsv` 里 515 行中有 8 行（位置 520–528）的 `DP/Ref_dp/Freq/DP4` 在修复后下降，因为这些 read 实际没有覆盖到那么远 |

修法：按实际比对到的 subject 片段计算 `ref_span`（`nchar(gsub("-", "", s))`）、
`ref_end`、`ref_cov = min(ref_span/ref_length, 1)` 与 `identity = 1 - nm/pmax(ref_span,1)`。
上游 Linux 同样存在该硬编码（`R/align.R:247-250`），因此记为 **L13**，属于需要回灌的上游缺陷。

**影响面**：只影响显式使用 `--aligner r`（默认 `minimap2` 一直是对的）。功能回归
（168 个运行，默认 minimap2）结果**逐行不变**；跨版本比对（两端都用 `aligner="r"`）
出现可解释差异，见 §5。

## 4. 新增/更新的验证

| 验证 | 结果 |
|---|---|
| testthat | **48 个用例 / 192 个断言全通过**（新增：L13 单测、`--min-ref-coverage` 转发、`cache` 子命令、`doctor --check-online` 离线失败、`--clear-cache` 单独可用、usage 文本完整性） |
| GUI 自测（7 个脚本） | 全部 exit 0（`test_annotation_gui.py` 增加 6g/6h/6i 三节共 27 个断言） |
| 安装器逻辑（9 个脚本） | 全部 exit 0 |
| `R CMD check` | **Status: OK** |
| 功能回归（168 运行） | **FUNCTIONAL BASELINE MATCHED**（L13 不影响默认 minimap2 路径） |
| 压力矩阵 A–D | 见 §6（47 PASS / 0 FAIL / 2 SKIP） |
| 跨版本一致性 | **CROSS-VERSION COMPARISON OK**（差异全部归因到 L4/L10/L11/L13，见 §5） |

## 5. Linux 与 Windows 一致性（本轮重点）

同一数据（`01_data/TSM20260826/E4-3`）、同一 `aligner = "r"`、两端各跑两遍：

| 项目 | 结果 |
|---|---|
| Mode A `haplotypes.tsv` | 4 × 13，**完全一致**（单倍型、计数、比例、变异描述一个不差） |
| Mode A `variants.tsv` | 515 × 12；只有 `DP / Ref_dp / Freq / DP4` 四列在 **8 行**（位置 520–528，参考末端）上不同——正是 L13 修掉的"read 覆盖不到却计入深度"；`Pos/Ref/Alt/Filter_Status` 全部一致 |
| Mode A `qc.tsv` | 只有 `mean_identity`（0.994174 vs 0.994173，差 1e-6）与 `mean_coverage`（Linux 415.0000 = reads 条数；Windows 414.8412 = 真实覆盖）不同 |
| Mode C `haplotypes.tsv` | 290 × 9，**完全一致** |
| `annotation.tsv`（离线 cds） | 除"与目的序列完全一致"那一行的标签（Linux `synonymous` → Windows `no_variant`，L4）外**完全一致** |
| Mode B | Windows 两遍**完全一致**；上游未固定种子，同一输入在不同 RNG 状态下实测 29 vs 30 簇（脚本现场复测并打印） |
| `run_manifest.json` | Windows 新增 `status`/`log_path`；`protein_verified` 如实报告（L10） |

结论：**数值结论一致**；差异四类（L4 标签、L10 字段、L11 种子、L13 覆盖度），每一类都有
判别性证据与单测，没有"说不清的差异"。

## 6. 压力矩阵与发行

- 压力矩阵：`03_dependence/stress/run_stress_tests.py --group A,B,C,D`（结果见
  `tmp/test_results/stress_r3/stress_results.tsv`）；C 组新增的缓存/网络命令由
  testthat 覆盖。
- 发行：重建 `release/01_R-package/nanoamp_0.1.0.tar.gz`（91,286 B）与
  `release/03_GUI/nanoamp.exe`（11,310,235 B），重打两个资产并刷新
  `release/_build/SHA256SUMS.txt`（setup `c5da763b…`，offline-deps 未变 `2db72289…`）；
  离线沙箱安装 `install exit=0` + 安装树 CLI 注释端到端复验
  （`cache` / `call --clear-cache` 均可单独调用；注释 12 行 / 变异明细 22 行）；
  冻结 GUI exe 字符串检查 21 个关键字符串全部存在。

## 7. 仍未做

1. **上游回灌（P2-4）**：L1–L13 与 Windows 侧的 batch 空目录清理都应回到 Linux 仓库，
   按约定未擅自修改另一个仓库；
2. 压力矩阵中 C4（磁盘满）、C9（ARM64）、E2（高 DPI 125%/150%）仍需真机手工验证；
3. GUI 大表虚拟化/分页（P2-2）未做：B3 场景（41 单倍型 × 1 转录本）实测 15–17 s 内完成、
   界面不卡，但 500+ 行 × 多转录本的极端矩阵未做专门优化；
4. 未发布任何 GitHub Release。
