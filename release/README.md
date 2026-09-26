# nanoamp 发布包

本目录下的两个 zip 可直接作为 GitHub Release 资产上传，其余内容为它们的源材料。

## 目录结构

根目录只存放使用者解压后需要看到的内容与安装器源码；打包相关文件位于
`_build/`（详见 `_build/README.md`）：

```text
release/
|-- install.exe           ← 使用者双击这个（约 12 MB）
|-- uninstall.exe         ← 卸载器
|-- README.md             ← 使用者看到的说明
|-- 01_R-package/         R 包版：需要编写 R 代码的用户
|-- 02_CLI/               命令行版：需要批量处理样本的用户
|-- 03_GUI/               图形界面版：不使用命令行的用户（最常用）
|-- deps/                 固定版本依赖清单（联网安装用；进 setup zip）
|-- _offline/             离线依赖源材料：R 安装器 + 109 个 R 包 + minimap2
|-- _installer/           安装器/卸载器源码与自测（开发者用；含 diagnose_install_env.*）
`-- _build/               打包工作区（开发者用；zip 在这里生成，不进 Git）
    |-- build_assets.py       重新生成两个 zip（内容逐条自校验）
    |-- SHA256SUMS.txt        产物的 sha256，随仓库提交，便于对账
    |-- nanoamp-0.1.5-windows-setup.zip          ← 上传这个（约 34 MB，**单独也能装**）
    `-- nanoamp-0.1.0-windows-offline-deps.zip   ← 可选：装上就不用联网下载依赖（约 248 MB）
```

> 需要采集安装环境信息时，使用 `release/_installer/diagnose_install_env.bat`（或同名 `.py`）。

两个资产的内部结构共用一个根目录 `nanoamp-windows/`：

```text
nanoamp-windows/            ← 解压到同一个地方（两个 zip 会自动合并）
|-- install.exe  uninstall.exe  README.md
|-- 01_R-package/  02_CLI/  03_GUI/
|-- deps/                    ← 固定版本清单 pinned-R4.6.tsv（联网安装要用）
|-- bin/minimap2.exe         ← 比对程序（两个资产里是同一个文件）
`-- _offline/                ← 来自 nanoamp-0.1.0-windows-offline-deps.zip（可选）
```

### 仅解压 setup 包时的联网安装

`deps/pinned-R4.6.tsv` 记录了 109 个 R 依赖包各自的确切版本、大小、md5/sha256
和依赖关系（由 `deps/build_pinned_manifest.py` 从离线包生成）。安装时按以下方式处理：

1. 旁边存在 `_offline/` 时，直接离线安装，不访问网络（耗时最短，不受镜像状态影响）；
2. 没有 `_offline/` 时，先并发测速选源（清华 TUNA / 中科大 / 北外 / 南大 / 阿里云 /
   CRAN 官方），再按依赖顺序下载清单里指定的那些版本，逐个读取 zip 内的
   `Package`/`Version` 校验（版本必须一致；sha256 相同则额外记为"与离线包逐字节一致"），
   最后一次性安装并校验关键包能否加载；
3. 机器上没有 R 时，R 4.6.1 运行时也从同一镜像下载（大小与 sha256 与离线包里一致）。

> 验收采用"版本"而不是"字节"的原因：镜像会重新编译二进制，同版本不同字节属常态
> （例如 `generics_0.1.4.zip` 官方今天 86,409 B，离线包里 85,804 B）。
> 109 个固定版本目前均可从镜像获取；无法获取时安装器会明确报错并建议改用离线包。

比对程序 `minimap2.exe` 约 1.3 MB，setup 包内也带一份（`bin/minimap2.exe`），
安装时复制到 `<安装目录>\bin\`。因此只解压 setup 包的机器也可直接执行比对，
不会出现依赖已装好但缺少 minimap2 的情况。离线依赖包内的
`_offline/minimap2.exe` 是同一个文件，两个资产无论解压先后都不会冲突。

> **248 MB 的离线依赖包超过 GitHub 单文件 100 MiB 的硬限制，因此 zip 不进 Git**
> （`.gitignore` 已排除 `release/_build/*.zip`）；仓库里只提交
> `_build/SHA256SUMS.txt` 与 `deps/pinned-*.tsv`。

## 重新生成资产

```powershell
# 1. R 包 tarball（含当前源码：路径修复与功能注释都在里面）
R CMD build 02_code/r --no-build-vignettes
copy nanoamp_0.1.0.tar.gz release\01_R-package\

# 2. 图形界面 exe
python 02_code\PythonGUI\build_exe.py
copy 02_code\PythonGUI\dist\nanoamp.exe release\03_GUI\

# 3. 安装器与卸载器 exe
python release\_installer\build_exe.py

# 4. 固定版本依赖清单（离线包换了内容时才需要；平时已提交在 release/deps/）
python release\deps\build_pinned_manifest.py

# 5. 打包成两个资产 zip（写进 release\_build\），并重写 _build\SHA256SUMS.txt
python release\_build\build_assets.py

# 6. 只校验（不重建）：解压后每条内容与源材料逐字节比对
python release\_build\build_assets.py --verify-only
```

`build_assets.py` 用固定时间戳写 zip，因此相同的源材料生成相同的字节；
它会把产物解压回来、逐条与源文件比对 sha256，不一致即报错退出。

### 与本仓库已发布资产对账

```powershell
# 先下载已发布的资产（例如 v0.1.3）
gh release download v0.1.3 -D tmp\published
python release\_build\build_assets.py --compare-published tmp\published\<setup.zip> tmp\published\<offline-deps.zip>
```

该命令会列出条目差异与 CRC 不一致的文件（离线依赖包 113 个文件中，112 个与 v0.1.2 的
资产完全一致，唯一差异是 `PACKAGES` 索引的行尾：发布版为 CRLF，仓库里为 LF，
内容逐行相同）。

## 上传

**已发布的版本：v0.1.3 与 v0.1.5**。当前仓库里的 setup 包比已发布的 v0.1.5 更新
（含一轮 GUI 修复），**尚未上传**：

```text
已发布  : https://github.com/Clearmind777/Nanoamp_for_win/releases/tag/v0.1.3
          tag v0.1.3
          asset nanoamp-0.1.3-windows-setup.zip  33,198,534 B
                 sha256 f408872787bf74ec5ae2146b9c07d2fc928ddc640a3c57fd8d54242a37a75e6a

已发布  : https://github.com/Clearmind777/Nanoamp_for_win/releases/tag/v0.1.5
          asset nanoamp-0.1.5-windows-setup.zip
                 sha256 494886c61c8814543bd204d6fb8b6ce81fe1ef12e571bf3131b885053a3b5384
          asset nanoamp-0.1.0-windows-offline-deps.zip
                 sha256 2db72289a8ecef7e16ef388f8c6a8a59c1369b6c2212fcfa29d92297d9162d40

未发布  : release/_build/nanoamp-0.1.5-windows-setup.zip（同名，内容已更新）
          修掉三处 GUI 问题：关掉注释后不再显示上一次的 annotation.tsv、
          点「开始分析」清空结果页且可用「查看上次结果」回看、
          不勾选 PATH 时也能找到 minimap2（另：CDS「止」按目的序列长度预填）
          sha256 76e02f190ee29cf226d769b662638e9364fe32f229738e8996526d01c3dab1ba
          离线依赖包未变（sha256 2db72289…，重建结果逐字节一致）
          sha256 见 release/_build/SHA256SUMS.txt
```

> 同名不同内容：如果要把这一版发出去，请**新建一个 tag（例如 v0.1.6）**，
> 而不是把新文件覆盖到已发布的 v0.1.5 附件上 —— 已发布的校验值写在
> `RELEASE_NOTES-0.1.5.md` 里，覆盖会让下过旧包的人对不上账。

v0.1.3 发布时只上传了 setup 包：离线依赖包的内容自 0.1.0 起没有变化，已作为
**v0.1.2** 的附件发布（sha256 `16035340…`），发布说明直接链接到它。
**因此不要删除 v0.1.2 的 Release**，否则该链接会失效。
从 0.1.4 起 setup 包单独也能装完（联网下载固定版本的依赖），离线包只是耗时更短、
不受镜像状态影响的选项。

下次发版（示例：升到 0.1.6）：先改 `_build/build_assets.py` 里的 `SETUP_VERSION`
（当前仍是 `0.1.5`，因为这一版还没有定版本号），重建资产，然后

```powershell
gh release create v0.1.6 `
  release\_build\nanoamp-0.1.6-windows-setup.zip `
  --title "nanoamp 0.1.6 — Windows 版" --notes-file <说明.md>
```

或在 GitHub 网页上创建 tag 并上传。文件名不要修改：使用者按
`nanoamp-<版本>-windows-setup.zip` 查找安装包，`nanoamp-0.1.0-windows-offline-deps.zip`
的版本号保持 0.1.0（离线依赖本身没有变化）。

## 使用者操作流程

**只下载 setup 包也可以**（安装时会联网下载固定版本的依赖）：

1. 把 `nanoamp-0.1.5-windows-setup.zip` 解压到**路径不含中文和空格**的位置，例如 `D:\nanoamp\`
2. 双击解压出来的 **`install.exe`**，点「开始安装」；需要避免联网时，再把
   `nanoamp-0.1.0-windows-offline-deps.zip` 也解压到同一个 `nanoamp-windows\` 里

安装完成后：

- 桌面出现 **「nanoamp 分析工具」** 快捷方式 → 双击打开图形界面
- 命令行里可以输入 `nanoamp doctor`、`nanoamp call ...`
- R 里可以 `library(nanoamp)`

不再需要时，双击 **`uninstall.exe`** 卸载。

详细的图文步骤见[仓库根目录的 README.md](../README.md)，以及各版本自己的 README。

## 本版包含的功能注释（可选）

`01_R-package/nanoamp_0.1.0.tar.gz` 与 `03_GUI/nanoamp.exe` 都包含**可选的功能注释**：
GUI 勾选「功能注释…」、命令行加 `--annotate-config`，程序就会把每条单倍型的变异
翻译成生物学后果，并多写 `annotation.tsv`（每个「单倍型 × 转录本」一行）与
`variants_annotation.tsv`（每个变异一行）。**不启用时输出与以前逐字节一致**
（有测试锁定这一点）。

- **不新增 R 依赖包**：注释复用已装的 Biostrings / jsonlite。包里自带两个示例配置
  （`example_cds.json` / `example_online.json`），**安装器会把它们复制到
  `<安装目录>\configs\`**（包里也留一份，`nanoamp doctor` 打印的 `configs` 一行是包里那份）；
- **两条路线**：`cds`（离线，自己给 CDS 坐标，长度须为 3 的倍数）与 `genome`
  （联网，程序在 GRCh38 定位扩增子并从 Ensembl 取转录本结构）。离线路线不需要网络；
  在线路线用系统的 `curl.exe`（Windows 10 1803 起自带）；
- **缓存**：参考序列切片缓存在 `%LOCALAPPDATA%\nanoamp\cache\ref`
  （可用 `--cache-dir` 或环境变量 `NANOAMP_CACHE_DIR` 改；`--no-cache` 本次跳过缓存，
  `--clear-cache` 清空）；
- **跳过与失败都会被记账**：注释被跳过时**退出码仍是 0**，原因写在 `qc.tsv` 的
  `annotation_skip_reason` 与 `run_manifest.json` 的 `annotation.skipped_transcripts`；
  加 `--strict` 可把它变成失败。在线路线取不到数据时会直接非零退出，不会静默降级。
- **失败的运行也留下档案**：`run_manifest.json` 现在有 `status`（`done`/`failed`/
  `cancelled`）、`error_class`（`input`/`environment`/`network`/`internal`）、
  `error_message` 与 `log_path`（`nanoamp.log`），GUI 按 `error_class` 给出对应的
  "怎么办"提示，而不再是一句通用报错；
- **GUI 新增**：「列出转录本」按钮（结果填进「转录本」下拉框，可指定某个 ENST）、
  「复制诊断信息」按钮（把运行日志整段复制到剪贴板）、「高级参数…」面板
  （比对方式/线程/各阈值，**只发送改动过的值**）、缓存一行（目录/占用/刷新/清空）
  与「测试 Ensembl 连接」，以及「注释结果 ↔ 单倍型结果」双向联动和可复制的蛋白序列窗口；
- **命令行新增**：`nanoamp cache [--clear]`、`nanoamp doctor --check-online`、
  `--min-ref-coverage`；`--clear-cache` 现在不需要输入文件即可单独使用；
- **`--aligner r` 的覆盖度修正**：该后端曾把每条 read 都当作覆盖整条参考序列
  （`ref_cov` 恒为 1、`mean_coverage` 等于 reads 条数），导致部分覆盖的 read 通过
  `--min-ref-coverage` 并被当成参考单倍型。现在按实际比对片段计算；默认的
  `minimap2` 后端一直是对的，本次只是补齐 `r` 的行为（详见教程附录 D）。

`make functional-test` 会用 `01_data/` 里 168 个真实运行与提交在
`03_dependence/baselines/functional/` 的基线逐行对比（Mode B 也逐字节一致，
因为随机聚类已固定种子）；`make stress-test` 跑环境压力矩阵（离线/代理/缓存损坏/
路径含空格与中文/超长路径/取消/并发等），两条命令都会在失败时以非零状态退出。

因此**发布资产的数量与布局没有任何变化**：仍然是
`nanoamp-0.1.5-windows-setup.zip`（安装器 + R 包 + GUI + minimap2 + 在线安装用的
固定版本清单）加上可选的 `nanoamp-0.1.0-windows-offline-deps.zip`（离线依赖）。
重建资产后 `_build/SHA256SUMS.txt` 里 setup 包的 sha256 会随之更新。

## 安装时可以修改的选项

`install.exe` 的窗口上方有两处可以调整：

| 项目 | 默认 | 说明 |
|---|---|---|
| **安装位置** | `%LOCALAPPDATA%\nanoamp` | 点「修改…」可以改到 `D:\nanoamp` 这类位置。「恢复默认」可以还原。窗口会显示该磁盘剩余空间 |
| **在桌面创建快捷方式** | ☑ 勾选 | 取消勾选则不创建快捷方式（适用于不希望改动桌面的情况） |
| **把 nanoamp 命令加入用户 PATH** | ☑ 勾选 | 取消勾选则只能通过完整路径调用 `nanoamp.cmd` |

安装到非默认位置时，安装器会把位置记录在
`%LOCALAPPDATA%\nanoamp.path`，**因此 `uninstall.exe` 仍能找到它**。
命令行启动器也从自身所在目录推断安装位置，不依赖默认路径。

## `install.exe` 执行的步骤

| 步骤 | 说明 |
|---|---|
| 1. 检查并安装 R | 先查找系统里已有的 R（要求 ≥ 4.2）：**仅当其版本与依赖包一致（当前 4.6）时才使用**；版本不一致（例如系统上是 R 4.5）则静默安装随包的 R 4.6 —— 它装在安装目录内的 `R\R-runtime`，**不会改动也不会卸载用户现有的 R** |
| 2. 安装 R 依赖包 | 旁边有 `_offline/r-packages/` 时**离线**安装 109 个包；没有则测速选源、按 `deps/pinned-R4.6.tsv` 的**固定版本**联网下载（校验 zip 内的 `Package`/`Version`），再一次性安装 |
| 3. 安装 nanoamp 主程序 | 从 `01_R-package/nanoamp_0.1.0.tar.gz` 安装 |
| 4. 注册 `nanoamp` 命令 | 生成 `nanoamp.cmd` 并把 `<安装目录>\bin` 加入用户 PATH（可取消） |
| 5. 安装比对程序 | 把 `bin/minimap2.exe`（或 `_offline/minimap2.exe`）复制到 `<安装目录>\bin\minimap2.exe` |
| 6. 创建桌面快捷方式 | 指向安装好的图形界面（可取消） |
| 7. 自检 | 检查包、依赖、minimap2 是否就绪 |

安装位置默认是 `%LOCALAPPDATA%\nanoamp`，**可以在窗口里修改**。

安装位置与副作用（**全部在用户目录内，不需要管理员权限**）：

```text
%LOCALAPPDATA%\nanoamp\          安装目录
  R\lib\                         109 个 R 依赖包 + nanoamp
  app\nanoamp.exe                图形界面
  bin\nanoamp.cmd                命令行启动器
  bin\minimap2.exe               比对程序
  config\                        生成的 R 驱动脚本与日志
  config.ini                     安装记录
%USERPROFILE%\Documents\.Renviron                 R_LIBS_USER 指向上面那个库
%USERPROFILE%\Desktop\nanoamp 分析工具.lnk       桌面快捷方式
用户 PATH                                        追加 %LOCALAPPDATA%\nanoamp\bin
```

卸载：双击 `uninstall.exe`（见下文），它会自动处理上述位置。

## 卸载

双击 **`uninstall.exe`** 后，它会：

1. 显示检测到的安装位置和占用空间；
2. 列出将要删除的内容（安装目录、桌面快捷方式、PATH 条目、`.Renviron` 行），
   逐项可以勾选；
3. 确认后删除，并报告释放了多少空间。

**不会删除**：用户自行安装的 R、用户的 R 库、用户的测序数据和结果文件。

> 只有随程序一起安装的 R（位于安装目录内的 `R\R-runtime`）才会作为可选项出现，
> 默认不勾选。

安装到非默认位置也不影响卸载：安装器会把位置记录在
`%LOCALAPPDATA%\nanoamp.path`；即使这个记录丢失，卸载器还会到用户 PATH
指向的目录里按特征文件查找。

## 两个 exe 的命令行用法

`install.exe` 和 `uninstall.exe` 都支持无界面模式，适用于批量部署或问题排查：

```bat
:: 安装
install.exe --silent                          :: 全自动，日志打印到控制台
install.exe --silent --no-shortcut            :: 不创建桌面快捷方式
install.exe --silent --no-path                :: 不修改 PATH
install.exe --silent --install-dir D:\nanoamp :: 指定安装位置
install.exe --check                           :: 只报告当前安装状态

:: 卸载
uninstall.exe --dry-run                       :: 只报告会删什么，不真删
uninstall.exe --silent                        :: 全自动卸载
uninstall.exe --silent --keep-runtime         :: 保留随程序安装的 R
```

> 注意：控制台模式需要能看到 stdout 的环境（普通 cmd / PowerShell 窗口），
> 直接双击不带参数时才弹图形窗口。

## 安装包组合说明：setup 包单独即可安装，两个 zip 建议解压到同一个文件夹

`install.exe` 和 `uninstall.exe` 各约 11 MB。**只解压
`nanoamp-0.1.5-windows-setup.zip` 即可完成安装**：`deps/pinned-R4.6.tsv` 里带着
依赖包的确切版本，安装器会自动测速选源、联网下载（约 159 MB，视网速 5–15 分钟），
`bin/minimap2.exe` 也已经在 setup 包里。

需要该步骤完全不联网时，把
`nanoamp-0.1.0-windows-offline-deps.zip`（约 248 MB）**也解压到同一个目录**
（两者都以 `nanoamp-windows/` 为根），安装器检测到 `_offline/` 即直接离线安装。

如果把 250 MB 依赖打进 exe，每次启动都要自解压，耗时更长且占用空间更多，因此离线依赖单独成包。

`uninstall.exe` 不依赖 `_offline/`，单独拷走也能用。

## 环境要求

- **Windows 10 / 11，64 位**
- **联网可选**：只装 setup 包时需要联网下载依赖；解压了离线依赖包则安装过程不需要联网
- 不需要管理员权限
- 首次安装约需 1.5 GB 磁盘空间（R 约 0.5 GB + 109 个 R 包约 0.35 GB + 余量）
- **不需要 conda，不需要 WSL**

## 离线依赖的来源（开发者）

```powershell
# 1. R 包 tarball
R CMD build 02_code/r --no-build-vignettes
copy nanoamp_0.1.0.tar.gz release\01_R-package\

# 2. 图形界面 exe
python 02_code/PythonGUI\build_exe.py
copy 02_code/PythonGUI\dist\nanoamp.exe release\03_GUI\

# 3. 离线依赖：R 安装器 + 109 个 R 包二进制 + minimap2.exe
#    由 03_dependence/offline-bundle/fetch_offline_bundle.R 获取（需要联网），
#    再按 release\_offline\ 的结构放好；minimap2.exe 也可用
#    03_dependence/windows-x86_64/build_minimap2.sh 重新编译。
#    打包成资产本身不需要联网。

# 4. 安装器与卸载器 exe
python release\_installer\build_exe.py
```

安装器自身的逻辑测试（不需要真正安装）：

```powershell
python release\_installer\test_installer_logic.py
python release\_installer\test_release_layout.py
python release\_installer\test_window_fit.py         # 窗口不会被内容挤出边界
python release\_installer\test_locked_file_retry.py  # 卸载时文件被占用会重试并报错
python release\_installer\test_copy_retry.py         # 安装时目标文件被占用会重试后报错
python release\_installer\test_r_version_choice.py   # 系统 R 与随包 R 的选择规则
python release\_installer\test_pinned_deps.py        # 固定版本清单、选源、minimap2 来源
```

发布前的三条整体验证（都会在失败时以非零状态退出）：

```powershell
Rscript 03_dependence\r-environment\run_tests.R          # testthat：39 个用例
python   02_code\PythonGUI\tests\test_annotation_gui.py  # 注释界面与容错
python   02_code\PythonGUI\tests\test_failure_reporting.py
make functional-test    # 168 个真实运行 vs 提交的基线
make stress-test        # 环境压力矩阵（A 组需要联网）
```
