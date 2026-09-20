# 工作报告 7：Windows / Linux 分仓与 Windows 版离网验证

> 日期：2026-09-20
> 关联：`work_report.6.md`
> 本轮范围：把原仓库拆成 Windows 与 Linux 两个独立仓库；对 Windows 仓库做离网验证

---

## 1. 摘要

原始单仓库 `a_09_18_26_mapping_programs_dev` 同时承载两个平台的内容。
本轮把它拆成两个**完整、独立、各自可运行**的仓库：

| 仓库 | 路径 | 定位 |
|---|---|---|
| Windows | `a_09_18_26_mapping_programs_dev_for_win` | 内置原生 `minimap2.exe`、MSYS2 编译方案、Windows R 环境脚本、离网安装包 |
| Linux | `a_09_18_26_mapping_programs_dev_for_linux` | 内置 Linux x86_64 minimap2/samtools、conda/源码获取说明 |

两个仓库都**保留完整 git 历史**，都是自包含可运行的，都不使用 conda 和 WSL。

Windows 仓库已完成**离网验证**：在屏蔽一切网络的前提下，从零安装 R 包依赖、
装好 `nanoamp`、跑通单元测试与全量功能回归，结果与联网基线完全一致。

---

## 2. 分仓方式

### 2.1 为什么不用分支/子目录

用户要求的是"分别独立成两个仓库"，因此没有采用"同仓库双目录"或"双分支"，
而是两个真正的独立仓库。这样两边可以各自独立演进（CI、README、依赖目录都不同），
不会出现一个平台的改动误伤另一个平台的情况。

### 2.2 复制的做法

从原仓库完整复制两份（含 `.git` 对象库），再各自按平台裁剪：

```text
原仓库 (27 commits, 2d70d08)
  |-- robocopy 全量 + .git  -->  _for_win     (保留全部历史)
  `-- robocopy 全量 + .git  -->  _for_linux   (保留全部历史)
```

复制时排除 `dist/`（291 MB 离线包，可用脚本重建）和构建产物，避免无谓搬运。

### 2.3 Windows 仓库的裁剪

**删除**（纯 Linux / macOS 内容）：

```text
03_dependence/linux-x86_64/      # Linux minimap2 + samtools 二进制
03_dependence/linux-arm64/
03_dependence/macos-x86_64/
03_dependence/macos-arm64/
03_dependence/fetch_dependencies.sh
```

**改写**：

| 文件 | 改动 |
|---|---|
| `03_dependence/README.md` / `README-CN.md` | 重写为 Windows 目录树 + Windows 支持矩阵；删掉 Linux/macOS 行；明确"不使用 conda / WSL" |
| `03_dependence/manifest.tsv` | 删除两行 linux-x86_64，只留 windows-x86_64 |
| `README.md` / `README-CN.md` | 加"Windows 变体 + 姊妹仓库"说明；外部工具章节改为内置 `minimap2.exe`；快速开始改为 PowerShell；新增 `ln_test_data` 链接层说明；`make` 目标更新 |
| `Makefile` | 删除 `fetch_dependencies.sh` 调用；新增 `toolchain` / `offline-bundle` / `offline-install`；`deps` 改为说明内置产物来源 |
| `.github/workflows/R-CMD-check.yaml` | 矩阵改为 `os: [windows-latest]` |
| `02_code/r/inst/docs/INSTALL_DEPENDENCIES{,-CN}.md` | 重写为纯 Windows：删掉 Linux/conda/WSL 章节，改为"minimap2 已内置，无需安装" |
| `02_code/README.md` / `02_code/r/README.md` | 补 Windows 变体说明；移除"Linux x86_64 内置"等表述 |

**保留**：`windows-x86_64/`（含编译好的 `minimap2.exe`）、`windows-arm64/`、
`r-environment/`、`offline-bundle/`、RInno 打包骨架、全部 `*.bat`/`*.ps1`。

### 2.4 Linux 仓库的裁剪

**删除**：

```text
03_dependence/windows-x86_64/    # 含 bin/minimap2.exe
03_dependence/windows-arm64/
03_dependence/r-environment/     # Windows 专用 R 环境脚本
03_dependence/offline-bundle/    # Windows 专用离线包脚本
02_code/r/inst/windows/          # RInno Windows 打包骨架
02_code/{cli,gui,r/inst/scripts}/*.bat
```

**改写**：`fetch_dependencies.sh`（删掉 `windows-*)` 分支）、
`.github/workflows/R-CMD-check.yaml`（改为 `ubuntu-latest`）、
`manifest.tsv`（删掉 windows 行）、以及对应的 README 文档集
（去掉 Windows/离线章节，改为 Linux 的 `devtools::test()` / `make check` 工作流）。

---

## 3. Windows 仓库离网验证

### 3.1 验证方法

要证明"离网可用"，必须让任何联网尝试都**立即失败**，否则"用了缓存"和"跑了网络"
无法区分。做法：

```powershell
$env:http_proxy  = 'http://127.0.0.1:9'   # 死端口
$env:https_proxy = 'http://127.0.0.1:9'
$env:no_proxy    = ''
```

同时把 R 库指向**只由离线包提供**的新目录，并用
`system.file(package=...)` 确认 `data.table` / `Biostrings` / `nanoamp`
确实解析自该目录，而不是系统里已有的库。

### 3.2 验证流程与结果

```text
1. 生成离线包
   Rscript 03_dependence/offline-bundle/fetch_offline_bundle.R
   -> closure complete, 109 个包, index visible 109/109, 291.1 MB

2. 执行仓库自带的离线安装脚本
   powershell -File 03_dependence/offline-bundle/install_offline.ps1 -RLib dist\R-lib-offline-test -RDir D:\tools\R
   -> 113 files verified            # SHA256 全量校验通过
   -> R already installed           # 复用已有 R，不重复安装
   -> local repository packages: 109
   -> verified present: 201 / 201   # 测试数据链接层修复并校验
   -> ALL TESTS PASSED (34 passed, 0 failed, 0 errors, 0 skipped)

3. 全量功能回归（只用离线库）
   Rscript 03_dependence/r-environment/run_functional_regression.R --modes A,B,C
```

| 指标 | 结果 |
|---|---|
| 离线包完整性 | 113 / 113 文件 SHA256 通过 |
| 本地仓库可见包数 | 109 / 109 |
| 安装到全新库的包数 | 109 |
| 单元测试 | **34 passed, 0 failed, 0 errors, 0 skipped** |
| 功能回归 | **168 / 168 runs ok**（31 个样本） |
| Mode A 复现公司变异 | **163 / 167 = 97.6%** |
| Mode A 100% 重合样本 | **22 / 23** |
| Mode C 平均 top1 占比 | **0.1231** |
| 实际使用的 minimap2 | `03_dependence\windows-x86_64\bin\minimap2.exe` (2.31-r1302) |

**结论：Windows 仓库在不联网的机器上可以完整部署并跑出与基线一致的结果。**

`163/167`、`22/23`、`0.1231` 三个关键数字与 `work_report.6.md` 记录的联网基线
逐位相同，说明离线路径没有引入任何行为差异。

### 3.3 验证过程中发现并修复的三个缺陷

这三个 bug 都会让离线包**表面生成成功、实际完全不可用**，值得记录：

**(1) `SHA256SUMS.txt` 写的是绝对路径。**
生成端用 `sub(paste0("^", dest, "/?"), ...)` 去前缀，但 Windows 下 `dest` 是反斜杠、
`list.files()` 返回混合形式，模式匹配不上，于是每条都保留了完整路径。
校验端再把绝对路径 join 到包目录上，自然全部失败（实测 "113 of 113 files failed
verification"）。现在两端都先统一成正斜杠，并写成相对路径——这也是清单可移植的前提。

**(2) `install_offline.ps1` 里混入了 R 的赋值符号。**
`$localRepo <- 'file:///' + ...` 在 PowerShell 中是语法错误
（`"< is reserved for future use"`），脚本根本跑不起来。

**(3) 查找 R 时只搜索子目录。**
`-RDir D:\tools\R\R-4.6.1`（直接给 R home）会被判为"未安装"，进而触发重复安装。
现在同时接受"安装根目录"和"R home"两种形式。

修复后重新验证，就是 3.2 的结果。

### 3.4 验证过程中的一个陷阱（方法论）

第一次做功能回归时，我先把测试库删掉了，结果 `run_functional_regression.R`
静默回落到系统已有的 `D:\tools\R\R-4.6.1\library`，跑出的"离线"结果其实没有
用到离线包。发现后重建离线库、重新确认 `system.file()` 解析路径，才得到 3.2
的结论。

**教训：验证"只用离线资源"时，必须显式断言依赖来自哪里**，
否则很容易把"系统里已经有"误当成"离线包可用"。

---

## 4. 两个仓库的现状

### 4.1 Windows 仓库

```text
03_dependence/
|-- manifest.tsv                      # 只有 windows-x86_64 一行
|-- README.md / README-CN.md          # Windows 目录树 + 支持矩阵
|-- licenses/minimap2-LICENSE.txt
|-- windows-x86_64/
|   |-- README.md
|   |-- install_msys2_toolchain.ps1
|   |-- build_minimap2.sh
|   `-- bin/minimap2.exe              # 1.33 MB, 静态链接
|-- windows-arm64/README.md
|-- offline-bundle/                   # 113 文件 / 291 MB（dist/ 不入库）
`-- r-environment/                    # R 环境 + 测试运行脚本
```

### 4.2 Linux 仓库

```text
03_dependence/
|-- manifest.tsv                      # 只有 linux-x86_64 两行
|-- README.md / README-CN.md          # Linux 目录树 + 支持矩阵
|-- fetch_dependencies.sh             # 已删掉 windows-*) 分支
|-- licenses/minimap2-LICENSE.txt
|-- linux-x86_64/bin/{minimap2,samtools}
|-- linux-arm64/README.md
|-- macos-x86_64/README.md
`-- macos-arm64/README.md
```

### 4.3 两边共同的约定

- 都不使用 conda，都不使用 WSL；
- 都保留完整 git 历史与 `00_materials/work_reports/`（历史日志不改写）；
- `01_data/ln_test_data` 仍是符号链接层（Windows 侧用
  `materialize_test_data.R` 一次性修复）；
- 各自 README 首页都写明自己是哪个平台的变体，并指向姊妹仓库。

---

## 5. 已知限制

1. **Linux 仓库未在本机验证。** 本机是 Windows，Linux 侧的
   `devtools::test()` / `R CMD check` 需要在 Linux 上跑。
   被删除/改写的脚本已做语法检查（`bash -n`）与引用扫描，但没有实机运行。
2. **两个仓库各自独立提交**，`_for_win` 从 `2d70d08` 的副本起步，因此它在
   基线仓库里"看不到"之后新增的 `60f3aa0`（SHA256 修复）。该修复以实际文件
   的形式包含在 Windows 仓库中，但两个仓库的历史不再逐位相同。
3. **未推送到 GitHub。** 上一轮已确认推送通道被网络层 reset；本轮两个新仓库
   都还没有配置 remote。
4. **离线包不含 Linux 内容**，符合 Windows 仓库定位；Linux 仓库没有离线包
   （其依赖通过 conda/系统包管理器/源码获取）。
5. Windows 仓库的 `dist/` 目前有 291 MB 本地文件（git 忽略）。若不需要留作
   验证证据，可删除后用 `fetch_offline_bundle.R` 重建。

---

## 6. 下一步

1. 在 Linux 机器上跑 Linux 仓库的 `devtools::test()` 与 `R CMD check`，
   确认裁剪没有破坏任何东西；
2. 为两个仓库分别配置 remote 并推送（需先解决推送通道问题）；
3. 在**真正没有 MSYS2** 的干净 Windows 机器上再验证一次 `minimap2.exe`
   与离线安装；
4. 继续推进 GTF / CDS 功能注释；
5. 用 RInno 构建 Windows 安装包。

---

## 7. 复现命令

```powershell
# --- Windows 仓库 ---
cd ...\a_09_18_26_mapping_programs_dev_for_win

# 生成离线包（有网机器）
Rscript 03_dependence\offline-bundle\fetch_offline_bundle.R

# 离网安装 + 自动跑测试（无网机器）
powershell -File 03_dependence\offline-bundle\install_offline.ps1 `
  -RLib dist\R-lib-offline-test -RDir D:\tools\R

# 只有单元测试
Rscript 03_dependence\r-environment\run_tests.R

# 全量功能回归
Rscript 03_dependence\r-environment\run_functional_regression.R `
  --outdir 04_results/r/test_run_win --modes A,B,C --threads 4
```

```bash
# --- Linux 仓库 ---
cd .../a_09_18_26_mapping_programs_dev_for_linux
bash 03_dependence/fetch_dependencies.sh     # 如未内置工具
Rscript -e 'devtools::test("02_code/r", reporter = "summary")'
make check
Rscript 02_code/r/inst/scripts/run_functional_tests.R --modes A,B,C --threads 4
```
