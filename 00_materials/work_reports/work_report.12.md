# 工作报告 12：本地数据层修复、路径含空格缺陷、文档更正

> 日期：2026-09-22
> 关联：`work_report.11.md`
> 本轮范围：本仓库在这台机器上的**本地副本已经不可用** —— 排查并修复数据层；
> 随后装上 R 环境跑通完整测试，过程中发现并修掉一个真实缺陷，并更正文档里的错误结论

---

## 1. 本轮结果一览

| # | 事项 | 结果 |
|---|---|---|
| 1 | 本地副本 `01_data/ln_test_data` 全部失效 | 完成：98 个 0 字节 `.fa` + 103 个缺失文件全部恢复，201/201 按 md5 校验通过 |
| 2 | `materialize_test_data.R` 是否认可 | 通过：`verified present 201/201`，`ALL ln_test_data LINKS RESOLVE TO THE CORRECT CONTENT` |
| 3 | 用真实数据跑功能回归 | 通过：mode A/B/C 各 **56/56**，`mean_overlap_rate` A=0.9807、B=0.5409，与 work_report.11 记录**完全一致** |
| 4 | R 单元测试 | 修复前 2 个 error（见 §3），修复后 **38/38 通过** |
| 5 | 发现并修掉真实缺陷 | 完成：`system2()` 参数未加 `shQuote()`，**输入路径含空格时 mode A/B 直接失败**（1 处代码、3 个调用点） |
| 6 | 文档更正 | 完成：`exact_reference_proportion` 被误标为"校正前"，实测推翻；`.fa` 的说明与生成脚本矛盾；悬空的 `§4.4` 引用 |
| 7 | 新增回归测试 | `test-core.R` 新增「比对不受路径中的空格影响」 |

---

## 2. 本地副本的数据层是怎么坏的

### 2.1 症状

`git archive` 式的副本（只导出被 Git 跟踪的文件、在 Windows 上把符号链接解成 0 字节）
留下的是这样一个链接层：

| 角色 | 文件数 | 状态 |
|---|---:|---|
| `consensus.*.fa` / `reference.self.fa` / `reference.wt.fa` | 98 | 存在但 **0 字节** |
| `reads.fastq` / `variants.*.xlsx` / `sanger.*.ab1` | 103 | **完全缺失** |

`manifest.tsv` 本身是好的：201 行，`target_path` 指向的 `test_data/` 原件**一个不缺**。
也就是说，坏掉的只是链接层，事实来源完好 —— 这正是 `materialize_test_data.R` 能修的场景。

### 2.2 修复

本机当时没有 R，因此先用一个语义完全照搬 `materialize_test_data.R` 的脚本把它修好：

```powershell
python tmp/repair_ln_test_data.py          # 逐行读 manifest.tsv，复制 + md5 校验
# materialized (copied) : 201
# ALL ln_test_data LINKS RESOLVE TO THE CORRECT CONTENT
```

之后再装好 R，用**仓库自己的** `materialize_test_data.R` 复核：

```text
manifest: 201 rows
materialized (copied) : 0
verified present      : 201 / 201
ALL ln_test_data LINKS RESOLVE TO THE CORRECT CONTENT
```

`copied = 0` 说明上一步的结果与官方脚本的期望逐字节一致。

### 2.3 `test_data/` 没有被改动

修复只写 `ln_test_data/`。`test_data/` 仅有的异常是一个 0 字节的
`ZNF8/2026.8.29-wt/WT_..._B11.fastq.fai`；代码里没有任何一处读 `.fai`
（`grep -r '\.fai\|indexFa' 02_code` 无命中），所以它不影响任何流程，未动。

---

## 3. 真实缺陷：输入路径含空格时比对失败（本次最重要的发现）

### 3.1 症状

装上 R 跑单元测试，11 个测试块里有 2 个 error：

```text
── Error ('test-core.R:65:3'): 方案 A 能在合成数据中恢复参考与突变单倍型 ──
Error: minimap2 alignment failed with exit code 1
── Error ('test-core.R:90:3'): 方案 B 能对合成数据产生簇并计数 ──
Error: minimap2 alignment failed with exit code 1
```

同样的数据、同样的命令手工跑 minimap2 却是**成功**的（exit 0，SAM 正常），
说明不是数据问题。

### 3.2 定位

`align_reads()` 把 minimap2 的 stderr 写进 `<out_bam>.minimap2.log`，把这个日志捞出来，
minimap2 自己把答案写在了里面：

```text
[ERROR] failed to open file 'E:\...\tmp\fixture': Permission denied
```

注意路径在**空格处被截断**了：`…\tmp\fixture` 后面本应是 ` with space\ref.fa`。

原因是 R 的 `system2()`（源码第一行就是答案）：

```r
command <- paste(c(shQuote(command), env, args), collapse = " ")
```

* `command` 由 `system2()` **自己加引号**；
* `args` **原样拼接**，路径里的空格于是把参数劈成了两个。

而 `align_reads()` 恰恰把 `normalizePath()` 的结果原样塞进 `args`：

```r
c("-ax", "map-ont", "--cs", "-t", as.integer(threads),
  normalizePath(reference_path, mustWork = TRUE),      # ← 没有 shQuote()
  normalizePath(reads_path,     mustWork = TRUE))      # ← 没有 shQuote()
```

### 3.3 为什么单元测试会撞上、而功能回归不会

`normalizePath()` 在 Windows 上会把 8.3 短名展开成长名：

```text
tempdir()   C:\Users\JALENZ~1\AppData\Local\Temp\...\RtmpXXXX      ← 没有空格
normalizePath → C:/Users/jalen zhong/AppData/Local/Temp/.../RtmpXXXX  ← 有空格了
```

单元测试用 `tempfile()` 造数据（落在 `tempdir()` 里），于是**任何用户名里带空格的机器**
（`John Smith`、`张 三`…）跑测试都会失败；而功能回归的输入输出都在仓库内
（`E:\...\Nanoamp_for_win\...`，无空格），所以 work_report.11 里 56/56 全绿，
这个缺陷就藏在了测试与真实使用之间的缝里。

### 3.4 影响面（这才是关键）

**用户把 FASTQ / 参考序列放在任何含空格的目录里，mode A 与 mode B 就完全不可用**，
报错信息只有一句 `minimap2 alignment failed with exit code 1`。
`D:\测序数据\样品 1\`、`C:\Users\John Smith\Desktop\` 这类路径在中国用户里非常常见。
README 里"路径不要含空格"的建议原本是为了绕开兼容性问题，实际上是在**掩盖**这个 bug。

顺带说明：**工具自身的路径不受影响** ——
`nanoamp_tool_path()` 返回的 `minimap2.exe` 是 `system2()` 的 `command`，会被自动加引号，
所以装在 `C:\Users\John Smith\AppData\Local\nanoamp\bin\` 也能跑。出问题的只是**数据路径**。

### 3.5 修复

`02_code/r/R/align.R`：给三个调用点的**路径参数**加 `shQuote()`，
并留注释说明「`command` 不要加、`stdout`/`stderr` 重定向路径不要加」——
后者是 R 自己打开的文件，加了引号反而会坏（已实测：`shQuote()` 重定向路径 → exit 1）。

```r
status <- system2(
  minimap2_bin,
  c("-ax", "map-ont", "--cs", "-t", as.integer(threads),
    shQuote(normalizePath(reference_path, mustWork = TRUE)),
    shQuote(normalizePath(reads_path, mustWork = TRUE))),
  stdout = sam, stderr = log_file          # 这两个不能加 shQuote
)
```

同时修掉同一类问题的另外两处：

| 位置 | 修改 | 说明 |
|---|---|---|
| `align.R` samtools `sort` / `index` | 路径参数加 `shQuote()` | Windows 默认走 `Rsamtools::asBam()`，不走 samtools，但 `use_samtools=TRUE` 时会踩 |
| `gui.R` `open` / `xdg-open` | 路径参数加 `shQuote()` | 非 Windows 分支；`fetch_offline_bundle.R:79` 早就是这个写法，保持一致 |

`utils.R:123` 的 `system2(path, "--version", ...)` **刻意不改**：`path` 是命令本身，
`system2()` 会自己加引号，再加一层 `shQuote()` 会直接报 `'"\"..."' not found`（已实测）。

### 3.6 防止再犯

`02_code/r/tests/testthat/test-core.R` 新增：

```r
test_that("比对不受路径中的空格影响", { ... 用 tempfile("nanoamp space ") 建目录 ... })
```

它先断言 `grepl(" ", normalizePath(td, winslash = "/"))` 确认路径里真的有空格，
再跑一次 mode A，断言得到唯一单倍型且 `is_reference` 为真。修复前该测试必然 error。

---

## 4. 文档更正

这一轮跑出了工具的真实输出，于是三处**与代码/数据矛盾**的说法被更正。

### 4.1 `exact_reference_proportion` 不是"校正前"的原始匹配率

`R/correct.R:191` 的定义清清楚楚：

```r
exact_reference_proportion = round(hap[is_reference == TRUE, sum(proportion)], 6)
```

它是**校正后**单倍型表里 `is_reference` 那一类的占比，因此**恒等于**
结果表里 `is_reference = 是` 那一行的占比。真正的"原始、未校正"比例是 mode C 的
`exact_any_proportion`（`R/exact.R:15-17`）。而 `README.md` 与 `tutorial.md` 原来把它
标成"原始/校正前"，还解释说"和 H2 一样是巧合"、"别的样本只有 2%–4%" —— 都是错的。

实测（本次回归输出，`TSM20260826/E4-3`）：

| 指标 | 来源 | 值 |
|---|---|---:|
| `exact_reference_proportion` | mode A `qc.tsv` | **0.314554**（= H2 的 31.5%，同一个量） |
| `exact_any_proportion` | mode C `qc.tsv` | **0.093607**（9.4%，这才是"一位不差"的原始 read 占比） |

顺带一提：`E4-9` 的 mode C 是 0.1356、`E4-19` 是 0.3268，所以"多数样本 2%–20%"的说法成立，
而"31.5% 是原始匹配率"不成立。已改 `README.md`（§1 的引言、§4 读表提示）与
`00_materials/tutorial.md`（§0.4、§1.4.2 的指标表与注解）。

### 4.2 `.fa` 不是"重新解析写出的 FASTA"

`ln_test_data/.gitignore`、`01_data/README.md`、`ln_test_data/README.md` 三处都说
`.fa` 是"把公司的 `.seq`/`.ab1` 解析后重新写出的 FASTA，复制不出来"。但：

* `prepare_test_data.R` 对**所有** role 一视同仁地建符号链接，`.fa` 的目标就是 `.seq`；
* `materialize_test_data.R` 对**全部 201 行**（含 `.fa`）做 md5 相等校验；
* 公司的 `.seq` 本身就已经是 FASTA（`>名字\r\nACGT…`）。

所以 `.fa` 与 `.seq` 逐字节相同；保留在 Git 里的真实理由只是**小**（98 个不到 100 KB）。
三处说明已改成这个说法。

### 4.3 悬空引用

`tutorial.md` 的 `§0.4` 引用"见 §4.4"，但全文没有 4.4 节（只有附录 A–D），
已改为指向 `§1.4.2`。

---

## 5. 验证清单

| 项目 | 结果 |
|---|---|
| `repair_ln_test_data.py` | 201/201 复制并 md5 校验通过；再跑一次 `already correct 201`（幂等） |
| `materialize_test_data.R`（官方脚本） | `verified present 201 / 201`，`copied = 0` |
| 恢复文件可用性 | `.fa` 可解析（`>名字` + 序列）、`.fastq` 记录数 4 的整数倍、`.xlsx` 可被 openpyxl 打开、`.ab1` 为 `ABIF` |
| minimap2 冒烟（E4-3） | 手工 `-ax map-ont` 成功产出 SAM；mode A QC 报 `mapping_rate` 0.997717（437/438 primary） |
| R 单元测试 `run_tests.R` | 修复前 24 passed / 2 errors → 修复后 **38 passed / 0 failed / 0 error** |
| 功能回归 mode A | **56/56 ok**，`mean_overlap_rate` 0.9807 |
| 功能回归 mode B | **56/56 ok**，`mean_overlap_rate` 0.5409，`mean_top1_proportion` 0.7324 |
| 功能回归 mode C | **56/56 ok**，`mean_top1_proportion` 0.1231 |
| E4-3 mode A `qc.tsv` 逐项 | 与 `tutorial.md` 摘录**完全一致**：438 / 437 / 426 / 0.997717 / 0.993877 / 573 / 4 / 12 / 0.333333 / FALSE / 0.314554 |
| 文档改动后的相对链接 | 全仓库扫描，0 处失效 |
| 独立副本比对 | 磁盘上另一份原始 `ln_test_data`（236 个文件、无 0 字节）与本次恢复的 **201/201 逐字节相同**，见 §5.1 |
| R 单元测试 `run_tests.R`（修复前 2 errors） | **38 passed / 0 failed / 0 error** |
| `R CMD check --no-manual`（CI 同款门槛） | **Status: OK**，含 `Running 'testthat.R' ... OK`，无 ERROR/WARNING/NOTE |
| CLI `doctor` | 通过：minimap2 2.31-r1302 找到、依赖全 TRUE、samtools 按文档缺失 |
| CLI `call`（E4-3, mode A） | 通过：`qc.tsv` 与 `haplotypes.tsv` **逐项复现**文档里的 438/437/426/0.997717/H1 33.3%/H2 31.5%`是`/H3 26.8%` |
| `test_release_layout.py` | **ALL DELIVERABLE CHECKS PASSED**（含两个 exe 的控制台模式、payload 哈希） |
| `test_installer_logic.py` | INSTALLER LOGIC OK |
| `test_install_path_validation.py` | PASS（13 合法 + 8 非法 + 真实「开始安装」处理函数） |
| `test_r_shortcut_cleanup.py` | PASS |
| `test_window_fit.py` | PASS 6/6 |
| `test_locked_file_retry.py` | 先 3/4（测试自身的环境假设，见 §5.2），**修好后 4/4** |
| `test_bundled_r_lookup.py` / `test_cancel_analysis.py` | PASS |
| `test_headless.py` | HEADLESS CHECKS OK |
| `test_e2e.py` | END-TO-END OK（真实跑一次 mode A 并解析输出） |
| `test_frozen.py` | FROZEN BUILD OK（现场用 PyInstaller 6.22.3 重新打包 `dist/nanoamp.exe`，10.8 MB，启动后稳定） |

### 5.1 独立副本比对（最强的一条证据）

本机 `E:\bioinfo\resource\software\src\nanoamp\ln_test_data` 是一份**完整的原始链接层**
（236 个文件：98 `.fa` + 32 `.fastq` + 42 `.ab1` + 29 `.xlsx` + 33 `.tsv` + 2 文档，
**没有一个 0 字节文件**）。用它逐个比对：

```text
mine vs pristine : same=201 diff=0 missing_in_pristine=0
```

即本次按 `manifest.tsv` 恢复的 201 个文件与独立来源**逐字节完全一致**，
且每个 `.fa` 都等于它对应的 `.seq`（`differing .fa = 0`）——§4.2 的文档更正由此得到独立佐证。

顺带记录一个上游事实：远端仓库里 `01_data/ln_test_data/**/*.fa` 是 **mode 120000**，
其 blob 内容（以 E4-3 为例，`55f66618…`）等于对应 `.seq` 的 **LF 规范化版本**，
而工作区里是 CRLF 版本。也就是说这些路径在 Git 里既不存"路径字符串"也不存 CRLF 原文；
在 Windows 上 checkout 得到的是可直接使用的 FASTA，这与本仓库"链接层 + materialize"的设计
自洽，但**不该**把它们当作普通内容文件提交（会引入整片行尾改动）。本次提交刻意不碰它们。

### 5.2 关于"文件被占用 → 重试"那条测试

`test_locked_file_retry.py` 第一个用例先失败在**测试自己**身上：
它把 `sys.executable` 复制成 `<install>\bin\nanoamp.exe` 再启动，用来模拟"用户没关窗口"。
本机该副本以 `0xC0000135`（STATUS_DLL_NOT_FOUND）秒退 —— 复制出来的 `python.exe`
找不到 `python313.dll`（不在同目录、也不在 PATH），于是根本不存在"被占用的运行中进程"，
卸载器第一次尝试就删干净了，断言"必须结束仍在运行的 nanoamp.exe"自然失败。
把解释器目录放进 PATH 后立刻 4/4，说明卸载器逻辑本身没问题。

已把这条环境依赖**修在测试里**（`release/_installer/test_locked_file_retry.py`）：
给替身进程注入一个 PATH 以解释器所在目录打头的环境，并在进程提前退出时打印退出码。
修复后在"PATH 里没有 Python"的条件下复测，输出为：

```text
结束仍在运行的 nanoamp.exe（PID 16644）
安装目录已删除（第 1 次尝试）
PASS  4/4 locked-file retry cases
```

---

## 6. 本机开发环境（按 `03_dependence/r-environment/README.md` 的标准位置）

```powershell
# R：一次性建好，全部离线，使用 release/_offline 里的安装器与 109 个包
. .\tmp\r_setup_and_verify.ps1
```

| 项目 | 位置 |
|---|---|
| R 4.6.1 | `D:\tools\R\R-4.6.1` |
| R 库 | `D:\tools\R\lib`（109 个包 + nanoamp 0.1.0） |
| `Rprofile.site` | `D:\tools\R\R-4.6.1\etc\Rprofile.site`（私有库 + TUNA 镜像） |
| Python 3.13.7（含 tkinter 8.6） | `D:\tools\Python313`（为了跑 GUI/安装器测试装的，未加入 PATH） |
| PyInstaller | 6.22.3（`python -m PyInstaller`，走 TUNA 镜像装） |

R 安装器用的是仓库自己的那套开关（`/VERYSILENT /NORESTART /CURRENTUSER
/SUPPRESSMSGBOXES /SP- /MERGETASKS="!desktopicon,!quicklaunchicon"`），
因此**没有**多出桌面或开始菜单的「R 4.6.1」图标。

日常用法：

```powershell
& "D:\tools\R\R-4.6.1\bin\Rscript.exe" --vanilla 03_dependence\r-environment\run_tests.R
& "D:\tools\R\R-4.6.1\bin\Rscript.exe" --vanilla 03_dependence\r-environment\run_functional_regression.R `
    --outdir tmp/test_results/r/test_run_win --modes A,B,C --threads 4

# GUI / 安装器测试（本机原 Python 没有 tkinter）
& "D:\tools\Python313\python.exe" 02_code\PythonGUI\tests\test_headless.py
& "D:\tools\Python313\python.exe" release\_installer\test_locked_file_retry.py
```

---

## 7. 远程推送（已准备就绪，被网络与凭据挡住）

### 7.1 目标与准备

* 远端：`https://github.com/Clearmind777/Nanoamp_for_win.git`（public，`main`）
  —— 由该账号的仓库列表确定，本工作区就是它的副本（`.git` 已丢失）。
* 提交已做好，放在 `tmp/push_clone` 里（**没有**动工作区）：

  ```text
  4d14184  fix: quote paths given to minimap2/samtools; correct QC metric docs
  5318beb  feat: add 取消操作 to install.exe, uninstall.exe and nanoamp.exe   ← 远端当前 main
  ```

  父提交就是远端 main 尖端，因此这是一次 **fast-forward** 推送；改动恰好 10 个文件
  （9 改 1 增），没有删除、没有动 `.fa`、没有动 `release/_offline`。

* 为了不下载 400 MB 负载，克隆用的是 `--depth=1 --filter=blob:none --no-checkout`
  （只取 102 个对象、26 KB），再把工作区内容补进工作树后提交。

### 7.2 挡在前面的两件事

| # | 阻塞 | 证据 |
|---|---|---|
| 1 | **网络到 github.com 时通时断** | 直连 5/5 失败（`Failed to connect to github.com port 443`、`Connection was reset`）；走本机 Clash（127.0.0.1:7890）3/3 为 `Connection was reset`；同一时段 `ls-remote` 偶尔成功（说明通道存在但不稳定） |
| 2 | **没有可用凭据** | 全局 `credential.helper=manager`，但 Git 的 exec-path 里只有 `git-credential-wincred.exe`（无 GCM）；`cmdkey /list` 无 github 条目；无 `~/.git-credentials`、无 `GH_TOKEN`/`GITHUB_TOKEN`、无 `gh` CLI；SSH 22 端口连接超时（`~/.ssh` 里的密钥是内网主机的，未注册到 GitHub） |

`tmp/push_retry.ps1` 会继续按"直连 / 代理"交替重试并写入 `tmp/push_retry.log`。
一旦网络窗口出现且凭据就绪，推送命令就是：

```powershell
git -C tmp\push_clone push origin main:main
```

---

## 8. 遗留与未验证

1. **提交尚未推送到 GitHub**：原因见 §7.2（网络 + 凭据，都不是仓库内容问题）。
   提交已在 `tmp/push_clone` 里就绪，`git push` 一次即可。
2. **`install.spec` / `uninstall.spec` 写的是 `onefile=False`（onedir），但产物实际是 onefile**：
   两个 spec 都没有 `exclude_binaries=True` + `COLLECT`，PyInstaller 因此把二进制打进 exe
   （所以启动时会自解压到 `_MEI*`）。`test_release_layout.py` 只用
   `"onefile=False" in text` 做字符串检查，锁不住这个语义。本轮不改构建配置，仅记录。
3. **`make offline-install` 与 `release/_offline` 的布局不同**：`install_offline.ps1` 面向
   `fetch_offline_bundle.R` 生成的 `dist/`（R 安装器在根目录 + `SHA256SUMS.txt`），
   而 `release/_offline` 是 `r/` 子目录、没有校验和清单。两条流程各自自洽，但不要混用。
4. `test_data/ZNF8/2026.8.29-wt/*.fastq.fai` 是 0 字节的遗留文件；无代码引用，未动。
5. 本轮**没有**改动 `00_materials/work_reports/work_report.11.md`（历史报告按约定原样保留），
   因此该文件 §5 关于"31.5% 是原始匹配率"的记述仍是旧的；结论以本报告 §4.1 为准。

> §7.1 的两条旧结论已作废：`install.exe` / `uninstall.exe` / `03_GUI\nanoamp.exe`
> 之前"起不来"是**沙箱**（受限用户）导致的 PyInstaller 自解压失败；在放开权限的环境里
> 三个程序都正常，控制台模式也有输出（见 §5 的 `test_release_layout.py` 一行）。
> Python GUI 测试"未跑"也已在装上带 tkinter 的 Python 后全部跑通。
