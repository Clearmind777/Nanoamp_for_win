# 工作报告 24：README 输入文件契约、`tmp/` 清理与 R 环境丢失

- 日期：2026-09-26
- 仓库：`Nanoamp_for_win`（Windows 专用）
- 上一轮：`work_report.23.md`（README-CN 同步、界面标题与路径分隔符、0.1.5 发布准备，提交 `ac29130`）
- 本轮委托：
  1. `tmp/` 能否清理（先只回答、不执行）→ 确认后按 **A 类**清理；
  2. 在仓库根 `README` 中补「输入文件契约」（最少要哪些文件、格式/命名要求、每个功能对应要准备什么），
     更新后同步远程仓库。

---

## 1. `tmp/` 按 A 类清理

先给出 A/B/C 三档分类（A：纯沙箱与可重建中间产物；B：仅本机有用但重建成本高的证据；
C：必须保留），**只回答不执行**。确认后只执行 A 类：

| 删除（A 类） | 内容 |
|---|---|
| 安装/在线沙箱 | 7 个早前沙箱安装目录 |
| 离线与资产自检 | `offline_test`、`offline_test2`、`asset_check`、`asset_check2`、`online_test`、`retry_test` |
| 构建中间产物 | `builds/`、`build2/`、`build3/`、`check/` |
| 探针与缓存 | 若干探针脚本、`__pycache__`、下载的 zip、`gh_*.json` |
| 测试输出 | `test_results/` 内容（保留仓库跟踪的 `test_results/README.md`） |

保留：`push_clone`（唯一 git 工作副本）、`xver`、`xver2`、`linux_lib`、各亚 MB 证据目录，
以及约 120 个验证脚本与日志。

结果：`tmp/` 由约 **4.9 GB** 降到 **1,099 MB / 2,061 个文件**（含隐藏项），其中
`push_clone` 工作区 590.9 MB + `.git` 503.6 MB、其余全部目录合计约 5 MB。
（清点一律带 `-Force`；不带 `-Force` 时会把 `.git` 漏掉，得到偏小的数字。）

## 2. R 环境丢失（本轮最重要的事故，机制未确认）

清理完成后曾完整跑通 testthat（48 用例 / 192 断言全绿）；随后要复跑一个
「日志追加写」检查时，`Rscript.exe` 报「无法识别」——`D:\tools\R` 已经**空了**：

- 消失内容：`D:\tools\R\R-4.6.1`（R 4.6.1 本体）与 `D:\tools\R\lib`（109 个固定版本包）；
- 时间：父目录 `LastWriteTime` 为 `2026/09/26 20:55:51`；
- 证据：回收站无痕迹（属程序化删除，不是资源管理器删除）、当时无安装器/R 进程在跑、
  且清理之后测试还是通过的（因此不是清理动作立刻造成的）；
- 推测：PowerShell 5.1 的 `Remove-Item -Recurse` 会**跟随 junction/符号链接**，
  清理时可能顺链删到了 `D:\tools`；但安装器本身不创建 junction，**未能证实**。

影响与不受影响的部分：

| 项目 | 状态 |
|---|---|
| R 侧验证（testthat、`R CMD check`、离线安装端到端） | 本轮**无法复跑**（R 不存在） |
| 仓库内容、git 历史、01_data、Python、GUI/安装器 exe | 不受影响 |
| 已构建的发布资产与 sha256（`494886c6…` / `2db72289…`） | 不受影响，**不要**重建（会改变校验值） |

恢复路径：`tmp/r_setup_and_verify.ps1` 从 `release/_offline/`（`r\R-4.6.1-win.exe` 与
`r-packages/`）离线重建 `D:\tools\R`，再安装 nanoamp 并跑测试。**本轮未执行**（等待指示）。

## 3. 根 README 补「输入文件契约」

`README.md` 原来只讲安装、界面、结果、排障，没有一处说明"到底要准备什么"。新增
**§2 输入文件契约（要准备什么）**，并把其后的章节顺延（首次安装 3 → 图形界面 4 →
结果解读 5 → 三种交付版本 6 → 故障排查 7 → 面向开发者 8），目录与正文里
`见 §4 的` 交叉引用一并改到 `§5`。

内容全部**以源码为准**（`02_code/r/R/cli.R` 的 options/usage、FASTQ/FASTA 读取实现、
注释配置校验、`batch` 样本表解析、`log_msg()` 的追加写、`align.R` 的阈值），
不写"设计意图"：

| 小节 | 要点 |
|---|---|
| 2.1 最少要准备的文件 | FASTQ + 目的序列 FASTA + 可写输出目录；并**明确列出不需要**参考基因组、GTF/GFF、公司 `.xlsx`、Sanger `.ab1` |
| 2.2 格式要求 | FASTQ：每条 read 四行、序列必须一行、行数为 4 的倍数、`@`/`+` 位置正确否则报错；`.gz` 按后缀**或魔数**识别；名称去 `@`；序列大写；**质量行只要求存在、不参与计算**；空文件报错。FASTA：必须有 `>` 头、**只用第一条**、缺失或空报错、路径与 MD5 入 manifest。长度关系写明 `--min-ref-coverage` 0.90 与 `--min-identity` 0.90 |
| 2.3 命名要求 | 程序**不要求**任何文件名；唯二约定是 GUI 自动填参考（`reference.self.fa` → `reference.fa` → `reference.wt.fa`）与 `batch` 样本表列名 `sample/reads/reference`（可选 `ref_label`，`sample` 会成为输出子目录名）。仓库自带的 `01_data/<数据集>/<样本>/` 单列一张表，避免被误读成程序要求 |
| 2.4 路径与文件系统 | 空格/中文可用；>260 字符且未开长路径时明确报错；结果表覆盖写、`nanoamp.log` **追加写**（同一输出目录重复运行会累积） |
| 2.5 用某个功能 → 需要准备什么 | 模式 A/B 需比对程序（内置 minimap2 或 `--aligner r`），模式 C 不需要；离线 CDS 注释需 `"route": "cds"` 配置且 **CDS 长度必须是 3 的倍数**；在线 genome 注释需联网且**锚定覆盖率 ≥ 90%**；批量需样本表 |
| 2.6 注释配置字段要求 | `route` 取值与推断规则、`cds.start/end` 必填且 1-based 闭区间、`cds.strand`、`cds.boundaries`（`inclusive`/`half_open`）、`genetic_code`、非法 JSON 直接报错（错误分类 `input`） |

`README-CN.md` 增加一节 **「输入文件契约（摘要）」**（放在命令行子命令之后），
用一张 7 行表覆盖同一契约并指向 `README.md` §2 的完整版，保证中英两份在**实质**上一致、
不会互相矛盾（中文版保持更短，符合四对 README 的既有做法）。

## 4. 验证

| 验证 | 结果 |
|---|---|
| 文档编码 | `README.md`、`README-CN.md` 均为 UTF-8 **无 BOM**、无替换字符（U+FFFD 计数 0） |
| 结构 | 新增 §2 六个小节标题齐全，其后章节编号连续（3–8），目录条目与正文一致 |
| 图表 | 三份窗口示意图仍由同一个生成脚本产出，审计 0 处错位（本轮未改图） |
| 提交内容 | 推送后远程 blob 与源文件 `hash-object` 完全一致：`README.md` `914fa605…`、`README-CN.md` `f49bbed1…` |
| R 侧测试 | **本轮未复跑**（R 环境丢失，见 §2）——本次仅改文档，不涉及 R 代码 |

### 4.1 全树一致性检查（补做）：发现 2 个从未提交的文件

顺手写了一个全树比对脚本 `tmp/check_tree_parity.py`：把源目录里每个受版本控制的文件
按 `.gitattributes` 的换行策略（**索引一律存 LF**，`eol=crlf` 只影响检出）规范化后
与 `HEAD` 的 blob 逐一比对。第一次比对报了 124 处"字节不同"，逐类看清楚后：

- 122 处是**换行差异**（源文件 CRLF、索引 LF），属策略内的正常现象；
- **2 处是真实的内容差异**——这两个文件在本机早已改好、却一直没有提交：

| 文件 | 磁盘上的内容 | `HEAD` 里落后的内容 |
|---|---|---|
| `02_code/r/inst/configs/README.md` | `01_data/<数据集>/<样本>/variants.N.xlsx` + 该样本的 `meta.tsv` | 重组前的 `01_data/test_data/**/variants.*.xlsx` |
| `02_code/r/inst/configs/example_cds.json` | `amplicon_reference` = `01_data/TSM20260826/E4-3/reference.self.fa` | 旧的 `01_data/test_data/TSM20260826-020-01254/E4-3_…seq` |

两者**都已在** `release/01_R-package/nanoamp_0.1.0.tar.gz` 里（4490 B / 757 B），
即用户拿到的包本来是对的、只有仓库历史落后，因此**不影响任何发布资产与校验值**。
已用 `d594b97` 补交（按指示只做本地提交、未推送）。补交后重跑脚本：
规范化后差异 **0**；仅剩 1 个未跟踪的运行残留 `release/nanoamp_install.log`
与 `tmp/` 下被脚本有意跳过的 1 个文件。

## 5. 提交与推送

- `61d14b0` `docs(readme): document the input-file contract in the root README`
  （`README.md` + `README-CN.md`）；`f5f88b1` 为本工作报告本身；两者提交后
  `git ls-remote origin main` 与本地 `HEAD` 一致，远程已同步。
- 之后改为**只本地提交、不推送**：`d594b97`（上表两个文件）留在本地
  `tmp/push_clone` 的 `main` 上，远程仍停在 `f5f88b1`，需要时说一声即可推送。

## 6. 仍未做

1. 恢复 `D:\tools\R` 并复跑 R 侧测试（脚本已就绪，见 §2）；
2. **GitHub Release 页面本身仍由使用者创建**（本机无 `gh`、无 `GITHUB_TOKEN`）：
   tag `v0.1.5`，目标 `main`，说明用 `release/RELEASE_NOTES-0.1.5.md`，
   附件 `nanoamp-0.1.5-windows-setup.zip` 与 `nanoamp-0.1.0-windows-offline-deps.zip`；
3. 上游回灌（Linux 仓库的 L1–L13）；
4. 需真机的压力用例：C4 磁盘满、C9 ARM64、E2 高 DPI 截图；
5. GUI 大表虚拟化/分页（P2-2，可选）。
