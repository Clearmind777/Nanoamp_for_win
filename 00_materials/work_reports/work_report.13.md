# 工作报告 13：01_data 去掉链接层、release/ 改成可直接发布的资产

> 日期：2026-09-22
> 关联：`work_report.12.md`
> 本轮范围：① 取消 `01_data` 的符号链接层，把规范化命名直接套到数据上，
> 并验证跑通（重点是 GUI）；② 把 `release/` 变成"可直接上传 GitHub Release 的资产压缩包"

---

## 1. 两项需求与结果

| # | 需求 | 结果 |
|---|---|---|
| 1 | `01_data` 的链接不切实际，取消它，直接对原始数据套用链接里的命名 | 完成：`ln_test_data/`、`manifest.tsv`、`prepare_test_data.R`、`materialize_test_data.R` 全部删除；数据变成 `01_data/<dataset>/<sample>/reads.fastq` 这样的普通文件，201 个文件逐个 md5 校验通过 |
| 2 | 验证跑通（主要是 GUI） | 完成：R 单测 38/38、功能回归 A/B/C 各 56/56、`R CMD check` Status: OK、**真实的 GUI 窗口跑完一次分析并显示出正确结果** |
| 3 | `release/` 改为可直接发布的资产压缩包（参考远程已上传的 release） | 完成：生成与远端 Release 同构的两个 zip（根目录 `nanoamp-windows/`）＋ `build_assets.py` ＋ `SHA256SUMS.txt`；解压即用、并在一台"干净沙箱"里实测安装成功、安装后 CLI 与 GUI 都能跑 |
| 4 | 版本 | setup 资产升到 **0.1.3**（`nanoamp-0.1.3-windows-setup.zip`），离线依赖包保持 `nanoamp-0.1.0-windows-offline-deps.zip`（内容未变） |

---

## 2. 01_data：取消链接层

### 2.1 之前的结构与问题

```text
01_data/test_data/           公司原始交付（文件名带样本/项目号/日期/孔位）
01_data/ln_test_data/        符号链接层 + manifest.tsv（201 行）
     <dataset>/<sample>/reads.fastq -> ../../test_data/...fastq
```

这套链接在 Windows 上很脆：git 只保存链接目标，没开开发者模式时 checkout 出来是
文本桩；本工作区这次更是被解包成 98 个 0 字节 `.fa` + 103 个缺失文件（见
work_report.12），需要 `manifest.tsv` + md5 校验 + `materialize_test_data.R` 才能修回来。
用户要求直接取消这一层。

### 2.2 现在的结构

```text
01_data/
|-- TSM20260826/<sample>/{reads.fastq, consensus.N.fa, reference.self.fa,
|                         reference.wt.fa, variants.N.xlsx, sanger.N.ab1, meta.tsv}
|-- ZNF8/<sample>/...
|-- nano_seq/<sample>/...
|-- SD260728184122_1/        公司结构化交付，无 FASTQ，保持原样
|-- SD260812174403_1/
|-- README.md                新的数据说明（命名规范、meta.tsv 列、怎么加样本）
`-- README-raw.md            原 test_data/readme.md（公司原始命名与目录结构说明）+ 抬头说明
```

* **文件即数据**：`01_data/<dataset>/<sample>/reads.fastq` 直接用，没有链接、没有清单。
  因为随仓库提交，clone 之后**不需要任何准备步骤**。
* **`meta.tsv` 记录来历**：每行是 `dataset / sample / role / cluster / file /
  source_dir / source_file / source_note`，`source_file` 就是公司交付时的原始文件名
  （例如 `E4-3_TSM20260826-020-01254_20260827-020-BAN05-5_H08.fastq`）。
  同一份公司文件被多个角色用到时（`reference.self.fa` 即本样本 cluster 1 的共识，
  `reference.wt.fa` 是另一个样本的共识），现在各自是目录里的一份副本 —— 分析要的是
  "文件就在那儿"，不是层层跳转。
* **不丢材料**：`test_data/` 里不在链接层的 138 个文件全部有了去处 ——
  两个 SD 批次原样搬上来；`ZNF8/ZNF8.dna`、WT 的 2 个 `.fai` 按原名放进
  `01_data/ZNF8/ZNF8.dna`、`01_data/ZNF8/WT/`；`readme.md` 变成 `README-raw.md`。

### 2.3 数据搬家的实现与校验

`tmp/restructure_data.py`（一次性脚本，dry-run 通过后执行）：

1. 读 `manifest.tsv` 的 201 行，把每行的 `target_path` 复制成
   `link_path` 去掉 `ln_test_data/` 之后的新路径；
2. **每复制一个文件立刻 md5 与源文件比对**，不一致就整脚本失败退出；
3. 生成 32 份 `meta.tsv`；
4. 搬走上面那批遗留文件与两个 SD 批次；
5. 只有前面全部通过，才删除 `ln_test_data/` 与 `test_data/`。

结果：`copied and verified: 201`、`wrote 32 meta.tsv files`，随后随机抽查 E4-3 的
`reads.fastq` / `reference.self.fa` / `variants.1.xlsx` / `sanger.1.ab1`，与磁盘上另一份
独立副本（`E:\bioinfo\resource\software\src\nanoamp\ln_test_data`）**逐字节一致**。

### 2.4 代码随之改动

| 文件 | 改动 |
|---|---|
| `02_code/r/inst/scripts/prepare_test_data.R` | **删除**（不再需要生成链接与 manifest） |
| `03_dependence/r-environment/materialize_test_data.R` | **删除**（不再需要修链接） |
| `02_code/r/inst/scripts/run_functional_tests.R` | 样本发现从"读 `manifest.tsv`"改成"遍历 `01_data/*/*/meta.tsv`"，读成一个同形的表，后续逻辑一行未改 |
| `02_code/r/tests/testthat/test-core.R` | 旧的「manifest 指向存在的软链接」测试 → 「每个样本目录都自带规范化文件与 meta.tsv」，并在 `01_data` 不可达时 skip（见 §4） |
| `02_code/r/tests/testthat/test-gui.R`、`run_analysis.R` | 示例路径改为 `01_data/TSM20260826/E4-3/...` |
| `02_code/PythonGUI/tests/{test_e2e,screenshot_populated}.py` | 同上 |
| `03_dependence/offline-bundle/install_offline.ps1` | 去掉调用 `materialize_test_data.R` 的那行 |
| `README.md`、`README-CN.md`、`01_data/README.md`、`03_dependence/*README*`、`02_code/r/README*`、`02_code/README*`、`00_materials/tutorial.md`、`.gitignore` | 路径与说明全部改写；历史报告按约定不动 |

`01_data/README.md` 重写为：目录结构、固定文件名、`meta.tsv` 列含义、怎么新增样本、
两个 SD 批次与 `README-raw.md` 的定位。

### 2.5 GUI 验证（本轮重点）

用真实 Tk 窗口跑（`tmp/gui_check.py`，操作的是窗口自己的"开始分析"处理函数）：

```text
reference box: ...\01_data\TSM20260826\E4-3\reference.self.fa      ← 选完 reads 自动填上
status: 分析完成，输出目录：...\tmp\test_results\gui_check\E4-3（12 条单倍型）
   OK   分析完成
   OK   12 haplotypes shown
   OK   top row is 33.33% with 218delG
   OK   the reference-matching haplotype is shown as 31.46% 是
   OK   third haplotype is 26.76%
   OK   QC tab shows mapping_rate 0.997717 / n_reads_total 438
   OK   selected reference sequence is 529 bp
GUI CHECK OK - the window ran the analysis and displayed the results
```

即：GUI 在新数据布局下**能选文件、能自动找到参考、能跑完、能把 12 条单倍型
（33.33% / 31.46% `是` / 26.76%）、QC 指标和选中序列显示出来**。

---

## 3. release/：两个可直接发布的资产

### 3.1 与远端 Release 对齐

远端 `Clearmind777/Nanoamp_for_win` 的 Release（v0.1.2）只有两个附件：

| 附件 | 大小 | 内部根目录 |
|---|---|---|
| `nanoamp-0.1.2-windows-setup.zip` | 31.0 MB | `nanoamp-windows/`（install.exe、uninstall.exe、01_R-package、02_CLI、03_GUI） |
| `nanoamp-0.1.0-windows-offline-deps.zip` | 248.2 MB | `nanoamp-windows/_offline/`（R 安装器、109 个 R 包、minimap2.exe） |

本轮生成的资产保持同样的双附件设计与 `nanoamp-windows/` 根目录，setup 升到 0.1.3：

| 附件 | 大小 | 说明 |
|---|---|---|
| `release/nanoamp-0.1.3-windows-setup.zip` | 33.3 MB（32 个文件） | 含**重建后**的 install.exe / uninstall.exe / 03_GUI/nanoamp.exe 与含 `align.R` 修复的 R 包 tarball |
| `release/nanoamp-0.1.0-windows-offline-deps.zip` | 248.0 MB（113 个文件） | 与已发布的离线依赖包内容一致 |

### 3.2 新增的工具与记录

* `release/build_assets.py`：把 `release/` 里的源材料打成一个 zip（固定时间戳 ⇒
  相同输入给出相同字节），**写完立刻解压回来逐条比 sha256**；`--verify-only` 只校验；
  `--compare-published <setup.zip> <deps.zip>` 与下载来的已发布资产对账（列条目差异与
  CRC 不一致的文件）。它会跳过 `build/`、`dist/`、`__pycache__` 这些中间目录
  （第一次打包时正是它们让 setup 包从 33 MB 虚胖到 59 MB）。
* `release/SHA256SUMS.txt`：两个 zip 的 sha256，随仓库提交。
  因为 **248 MB 的离线依赖包超过 GitHub 单文件 100 MiB 的硬限制，zip 不进 Git**
  （`.gitignore` 已排除 `release/nanoamp-*-windows-*.zip`），用 SHA256SUMS 对账。
* `release/README.md` 重写：两个资产是什么、内部结构、怎么重新生成、怎么上传
  （`gh release create ...`）、以及"两个 zip 必须解压到同一个目录"。

对账结果（与下载的 v0.1.2 两个附件逐条比）：

```text
setup   : 14 entries vs 14 entries      structure identical
          identical 6   differing 8     ← 重建的 exe / R 包 / README / CLI 启动器
offline : 113 entries vs 113 entries    structure identical
          identical 112 differing 1     ← 只有 PACKAGES 的行尾（CRLF vs LF）
```

8 个内容差异正好是"该变的"：`install.exe`、`uninstall.exe`、`03_GUI/nanoamp.exe`
（用当前源码 + PyInstaller 6.22.3 重建）、`01_R-package/nanoamp_0.1.0.tar.gz`
（含 align.R 修复）、`02_CLI/bin/nanoamp.cmd` 等三个启动器、以及 `README.md`
（本轮改写）。**没有任何结构差异**：两边都是 14 个条目、同样的
`nanoamp-windows/` 根目录、根下同一份 `README.md`，都**不含** `_installer/`
（安装器源码只留在仓库里，不随资产发布 —— 这一点是照着已发布资产核对出来的）。

离线依赖包里唯一的内容差异是 `PACKAGES` 的行尾：发布版 35,367 字节、仓库 34,311 字节，
逐行相同（1056 行、109 个包），差 1056 字节正好是 1056 个 `\r`。
其余 112 个文件（含 87.5 MB 的 R 安装器与 109 个包）完全一致。

### 3.3 资产验证：解压即用 → 干净沙箱安装 → 安装后实跑

1. **解压**：两个 zip 解到同一目录，得到
   `nanoamp-windows/{install.exe, uninstall.exe, 01_R-package, 02_CLI, 03_GUI, _installer, _offline(113 files)}`。
2. **控制台模式**：解压出来的 `install.exe --check`、`uninstall.exe --dry-run` 都有正常输出。
3. **沙箱静默安装**（把 `USERPROFILE`/`LOCALAPPDATA`/`APPDATA` 指到临时目录，
   所以真实用户目录**没有被写**）：

   ```text
   检测到已安装的 R 4.6：D:\tools\R\R-4.6.1\bin\Rscript.exe
   使用 R 4.6 对应的 109 个依赖包 … 关键依赖检查: TRUE
   * DONE (nanoamp)
   已创建命令行驱动 / 启动器 / minimap2 / 图形界面
   自检通过
   已写入配置 …\target\config.ini
   安装成功。
   ```

4. **安装后的产物实跑**：

   * `bin\nanoamp.cmd doctor` → 依赖全 TRUE、minimap2 找到；
   * `bin\nanoamp.cmd call --reads ...\01_data\TSM20260826\E4-3\reads.fastq
     --reference ...\reference.self.fa --mode A` → 8 个输出文件齐全，
     `qc.tsv` 为 438 / 437 / 426 / 0.997717 / … / `exact_reference_proportion` 0.314554，
     与文档里 E4-3 的数值逐项一致；
   * `app\nanoamp.exe` 启动后 10 秒仍在运行（冻结版 GUI 正常）。

---

## 4. 一处自己引进的回归（已修）

数据重构后 `R CMD check` 报 **Status: 1 ERROR**：

```text
── Failure ('test-core.R:139:3'): 01_data 的每个样本目录都自带规范化文件与 meta.tsv
Expected `length(meta_files)` > 0.  Actual comparison: 0.0 <= 0.0
```

原因：`R CMD check` 里测试跑在 `<pkg>.Rcheck/tests` 下，`project_root_test_root()`
向上四层落在 check 目录里，那里没有 `01_data`。旧的 manifest 测试在这种情况下会
`skip_if_not` 跳过，而我新写的测试是硬断言 —— 把"在仓库里必须通过"和"在 check 里
必须跳过"混在一起了。

修复：加一行 `skip_if_not(dir.exists(data_root), "01_data not available (e.g. under R CMD check)")`，
其余断言保持严格。之后 `R CMD check` 恢复 **Status: OK**，本地跑单测仍是 38/38、0 skipped。

---

## 5. 验证清单

| 项目 | 结果 |
|---|---|
| 数据搬家 | 201/201 复制并 md5 校验；抽查与独立副本逐字节一致 |
| 数据结构 | 32 个样本目录、32 份 `meta.tsv`、两个 SD 批次与遗留文件各就各位 |
| R 单元测试 | **38 passed / 0 failed / 0 error / 0 skipped** |
| 功能回归 mode A / B / C | **各 56/56 ok**；`mean_overlap_rate` 0.9807 / 0.5409（与重构前一致） |
| `R CMD check --no-manual` | **Status: OK**（testthat 全过） |
| GUI（真实窗口） | GUI CHECK OK：自动填参考、跑完分析、显示 12 条单倍型与 QC、选中行显示 529 bp 序列 |
| Python GUI 测试 | `test_headless` HEADLESS CHECKS OK；`test_e2e` END-TO-END OK；`test_frozen` FROZEN BUILD OK |
| CLI（仓库内） | `doctor` 正常；`call` 在 E4-3 上复现文档里的 QC 与单倍型表 |
| 资产构建 | 两个 zip 逐条 sha256 自校验通过；`SHA256SUMS.txt` 写入 |
| 资产与已发布附件对账 | setup 14 vs 14 条目、结构完全一致（6 个内容相同，8 个是重建产物）；离线依赖包 113 vs 113，112 个条目完全一致，唯一差异是 `PACKAGES` 的行尾 |
| 解压即用 | 解压布局与已发布资产一致；两个 exe 的控制台模式都有输出 |
| 沙箱全新安装 | 成功：找到 R → 装 109 包 → 装 nanoamp → 建启动器/快捷方式(跳过)/minimap2/GUI → 自检通过 |
| 安装后实跑 | `nanoamp doctor`、`nanoamp call`（qc.tsv 与文档一致）、`app\nanoamp.exe` 启动正常 |

---

## 6. 遗留

1. **release/ 里仍然保留源材料**（`install.exe`、`_offline/` 等）。它们是打包的输入，
   也是"直接在 release/ 里双击 install.exe 试装"所需（`install.exe` 要求 `_offline/`
   在旁边）。若希望 `release/` 只留两个 zip，可以把这些源材料移出 `release/`，
   但 `build_assets.py` 与 `test_release_layout.py` 的路径要跟着改。
2. **推送依赖不稳定的网络**：本轮提交（`refs/heads/main` = 见 §7）在本地已就绪，
   但 github.com:443 时通时断（直连经常 21 秒超时、代理被 reset），
   `git push` 需要等一个可用的窗口；release 资产走的是另一个 CDN，所以下载反而成功了。
3. `install.spec` / `uninstall.spec` 的 `onefile=False`（onedir）与实际 onefile 产物的
   不一致仍然存在（见 work_report.12 §8），本轮同样只记录未改。
4. 两个 SD 批次仍按公司原始结构保留（没有 FASTQ，不在样本命名体系内）。

---

## 7. 本轮提交与推送

```text
72fb58b  refactor(data)!: drop the 01_data link layer; ship release assets as zips
c0837dd  docs: note the report-only follow-up commits in work_report.12
```

改动规模：**新增 374 / 删除 418 / 修改 25**。删除的是
`01_data/test_data/**`（上游跟踪 283 个）与 `01_data/ln_test_data/**`（跟踪 133 个，
其余 103 个是 Windows 上物化出来、从未跟踪的副本）以及两个链接层脚本；
新增的是 `01_data/<dataset>/<sample>/**`（372 个）与
`release/build_assets.py`、`release/SHA256SUMS.txt`、本报告。

提交前做了两道核对：

1. `01_data` 在提交里的路径集合与工作区**逐个相同**（372 = 372）。
   这一步抓到一个真问题：克隆的工作树里还留着 103 个从未被跟踪的
   `ln_test_data/**` 副本（排除它们的 `.gitignore` 就在被删除的目录里），
   `git add -A` 会把它们当作新文件加回提交 —— 于是先整个清空 `01_data`
   再按工作区重建，问题消失。
2. 两个资产 zip（合计约 280 MB）**没有**被暂存（`.gitignore` 生效，脚本里也有断言）。

推送状态：见本文档所在的仓库 main 分支（截至本轮结束时，github.com:443 仍在不稳定状态，
每次 push 都会在 `RPC failed; curl 56 Recv failure: Connection was reset`
或 21 秒连接超时之间摆动；一旦有窗口即可推送）。
