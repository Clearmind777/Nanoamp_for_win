# nanoamp 发布包

这个目录里**两个 zip 就是可以直接上传到 GitHub Release 的资产**，其余是它们的源材料。

## 目录结构

根目录只放"使用者解压后要看到的东西"和安装器源码；打包相关的东西都在
`_build/` 里（详见 `_build/README.md`）：

```text
release/
|-- install.exe           ← 使用者双击这个（约 12 MB）
|-- uninstall.exe         ← 卸载器
|-- README.md             ← 使用者看到的说明
|-- 01_R-package/         R 包版：给要写 R 代码的同学
|-- 02_CLI/               命令行版：给要批量处理样本的同学
|-- 03_GUI/               图形界面版：给不写代码的人（最常用）
|-- deps/                 固定版本依赖清单（联网安装用；进 setup zip）
|-- _offline/             离线依赖源材料：R 安装器 + 109 个 R 包 + minimap2
|-- _installer/           安装器/卸载器源码与自测（开发者用；含 diagnose_install_env.*）
`-- _build/               打包工作区（开发者用；zip 在这里生成，不进 Git）
    |-- build_assets.py       重新生成两个 zip（内容逐条自校验）
    |-- SHA256SUMS.txt        产物的 sha256，随仓库提交，便于对账
    |-- nanoamp-0.1.5-windows-setup.zip          ← 上传这个（约 34 MB，**单独也能装**）
    `-- nanoamp-0.1.0-windows-offline-deps.zip   ← 可选：装上就不用联网下载依赖（约 248 MB）
```

> 装不上要采环境信息时用 `release/_installer/diagnose_install_env.bat`（或同名 `.py`）。

内部结构**共用一个根目录** `nanoamp-windows/`：

```text
nanoamp-windows/            ← 解压到同一个地方（两个 zip 会自动合并）
|-- install.exe  uninstall.exe  README.md
|-- 01_R-package/  02_CLI/  03_GUI/
|-- deps/                    ← 固定版本清单 pinned-R4.6.tsv（联网安装要用）
|-- bin/minimap2.exe         ← 比对程序（两个资产里是同一个文件）
`-- _offline/                ← 来自 nanoamp-0.1.0-windows-offline-deps.zip（可选）
```

### 只装 setup 包也能装完（联网）

`deps/pinned-R4.6.tsv` 记录了 109 个 R 依赖包各自的**确切版本**、大小、md5/sha256
和依赖关系（由 `deps/build_pinned_manifest.py` 从离线包生成）。安装时：

1. 旁边有 `_offline/` → 直接离线安装，**完全不联网**（最快、最稳）；
2. 没有 `_offline/` → 先并发测速选源（清华 TUNA / 中科大 / 北外 / 南大 / 阿里云 /
   CRAN 官方），再按依赖顺序下载**清单里那些版本**，逐个读 zip 里的
   `Package`/`Version` 校验（必须是同一版本；sha256 相同则额外记为"与离线包逐字节一致"），
   最后一次性安装并校验关键包能否加载；
3. 机器上连 R 都没有时，R 4.6.1 运行时也从同一镜像下载（大小与 sha256 与离线包里一致）。

> 为什么要按"版本"而不是"字节"验收：镜像会重新编译二进制，同版本不同字节是常态
> （例如 `generics_0.1.4.zip` 官方今天 86,409 B，离线包里 85,804 B）。
> 109 个固定版本目前都还能从镜像取到；取不到时安装器会明确报错并建议改用离线包。

比对程序 `minimap2.exe` 约 1.3 MB，**setup 包里也带一份**（`bin/minimap2.exe`），
安装时复制到 `<安装目录>\bin\`。所以只装 setup 包的机器也能直接跑比对，
不会出现"依赖装好了但没有 minimap2"的情况。离线依赖包里的
`_offline/minimap2.exe` 是同一个文件，两个资产谁先解压都不会冲突。

> **248 MB 的离线依赖包超过 GitHub 单文件 100 MiB 的硬限制，因此 zip 不进 Git**
> （`.gitignore` 已排除 `release/_build/*.zip`）；仓库里只提交
> `_build/SHA256SUMS.txt` 与 `deps/pinned-*.tsv`。

## 重新生成资产

```powershell
# 1. R 包 tarball（含当前源码，例如 align.R 的路径修复）
R CMD build 02_code/r --no-build-vignettes
copy nanoamp_0.1.0.tar.gz release\01_R-package\

# 2. 图形界面 exe
python 02_code\PythonGUI\build_exe.py
copy 02_code\PythonGUI\dist\nanoamp.exe release\03_GUI\

# 3. 一键安装器 + 一键卸载器 exe
python release\_installer\build_exe.py

# 4. 固定版本依赖清单（离线包换了内容时才需要；平时已提交在 release/deps/）
python release\deps\build_pinned_manifest.py

# 5. 打包成两个资产 zip（写进 release\_build\），并重写 _build\SHA256SUMS.txt
python release\_build\build_assets.py

# 6. 只校验（不重建）：解压后每条内容与源材料逐字节比对
python release\_build\build_assets.py --verify-only
```

`build_assets.py` 用固定时间戳写 zip，所以同样的源材料给出同样的字节；
它会把产物解压回来、逐条与源文件比 sha256，不一致就直接报错退出。

### 与本仓库已发布资产对账

```powershell
# 先下载已发布的资产（例如 v0.1.3）
gh release download v0.1.3 -D tmp\published
python release\_build\build_assets.py --compare-published tmp\published\<setup.zip> tmp\published\<offline-deps.zip>
```

会列出条目差异与 CRC 不一致的文件（离线依赖包 113 个文件里 112 个与 v0.1.2 的
资产完全一致，唯一差异是 `PACKAGES` 索引的行尾：发布版是 CRLF，仓库里是 LF，
内容逐行相同）。

## 上传

**v0.1.3 是最后一个已发布的版本，v0.1.4 与 v0.1.5 都还没有发布**：

```text
已发布  : https://github.com/Clearmind777/Nanoamp_for_win/releases/tag/v0.1.3
          tag v0.1.3 → a00c83c
          asset nanoamp-0.1.3-windows-setup.zip  33,198,534 B
                 sha256 f408872787bf74ec5ae2146b9c07d2fc928ddc640a3c57fd8d54242a37a75e6a

未发布  : release/_build/nanoamp-0.1.5-windows-setup.zip
          0.1.4 增加了"没有离线包也能联网安装（固定版本、自动选源）"
          0.1.5 补上 bin/minimap2.exe（联网装的机器也有比对程序）
                    + GUI 直接按 <安装目录>\bin\minimap2.exe 定位比对程序
          sha256 见 release/_build/SHA256SUMS.txt
```

v0.1.3 发布时只上传了 setup 包：离线依赖包的内容自 0.1.0 起没有变化，已经作为
**v0.1.2** 的附件发布（sha256 `16035340…`），发布说明直接链接到它。
**因此不要删除 v0.1.2 的 Release**，否则那个链接会失效。
从 0.1.4 起 setup 包单独也能装完（联网下载固定版本的依赖），离线包只是"更快更稳"的选项。

下次发版：先更新 `_build/build_assets.py` 里的 `SETUP_VERSION` 与文件名，重建资产，然后

```powershell
gh release create v0.1.5 `
  release\_build\nanoamp-0.1.5-windows-setup.zip `
  --title "nanoamp 0.1.5 — Windows 版" --notes-file <说明.md>
```

或在 GitHub 网页上建 tag + 上传。名字不要改：使用者按
`nanoamp-<版本>-windows-setup.zip` 找安装包，`nanoamp-0.1.0-windows-offline-deps.zip`
的版本号保持 0.1.0（离线依赖本身没有变化）。

## 使用者怎么用

**只下 setup 包也行**（安装时会自动联网下载固定版本的依赖）：

1. 把 `nanoamp-0.1.5-windows-setup.zip` 解压到**路径不含中文和空格**的位置，例如 `D:\nanoamp\`
2. 双击解压出来的 **`install.exe`**，点「开始安装」；想避免联网就再把
   `nanoamp-0.1.0-windows-offline-deps.zip` 也解压到同一个 `nanoamp-windows\` 里

装完之后：

- 桌面出现 **「nanoamp 分析工具」** 快捷方式 → 双击打开图形界面
- 命令行里可以输入 `nanoamp doctor`、`nanoamp call ...`
- R 里可以 `library(nanoamp)`

不想用了就双击 **`uninstall.exe`** 卸载。

详细的图文步骤见[仓库根目录的 README.md](../README.md)，以及各版本自己的 README。

## 安装时可以改的东西

`install.exe` 的窗口上方有两处可以调整：

| 项目 | 默认 | 说明 |
|---|---|---|
| **安装位置** | `%LOCALAPPDATA%\nanoamp` | 点「修改…」可以改到 `D:\nanoamp` 这类位置。「恢复默认」可以还原。窗口会显示该磁盘剩余空间 |
| **在桌面创建快捷方式** | ☑ 勾选 | 取消勾选就不建快捷方式（适合不想动桌面的情况） |
| **把 nanoamp 命令加入用户 PATH** | ☑ 勾选 | 取消勾选则只能通过完整路径调用 `nanoamp.cmd` |

装到非默认位置时，安装器会把位置记录在
`%LOCALAPPDATA%\nanoamp.path`，**所以 `uninstall.exe` 仍能找到它**。
命令行启动器也是从自身所在目录推断安装位置的，不依赖默认路径。

## `install.exe` 做了什么

| 步骤 | 说明 |
|---|---|
| 1. 检查并安装 R | 先找系统里已有的 R（要求 ≥ 4.2）：**只有当它的版本和依赖包一致（当前 4.6）时才用它**；版本不一致（例如机器上装的是 R 4.5）就静默安装随包的 R 4.6 —— 它装在安装目录内的 `R\R-runtime`，**不改动也不卸载你现有的 R** |
| 2. 安装 R 依赖包 | 旁边有 `_offline/r-packages/` 就**离线**装 109 个包；没有就测速选源、按 `deps/pinned-R4.6.tsv` 的**固定版本**联网下载（校验 zip 内的 `Package`/`Version`），再一次性安装 |
| 3. 安装 nanoamp 主程序 | 从 `01_R-package/nanoamp_0.1.0.tar.gz` 安装 |
| 4. 注册 `nanoamp` 命令 | 生成 `nanoamp.cmd` 并把 `<安装目录>\bin` 加入用户 PATH（可取消） |
| 5. 安装比对程序 | 把 `bin/minimap2.exe`（或 `_offline/minimap2.exe`）复制到 `<安装目录>\bin\minimap2.exe` |
| 6. 创建桌面快捷方式 | 指向安装好的图形界面（可取消） |
| 7. 自检 | 检查包、依赖、minimap2 是否就绪 |

安装位置默认是 `%LOCALAPPDATA%\nanoamp`，**可以在窗口里改**。

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
%USERPROFILE%\Desktop\nanoamp 分析工具.lnk        桌面快捷方式
用户 PATH                                         追加 %LOCALAPPDATA%\nanoamp\bin
```

卸载：双击 `uninstall.exe`（见下文），它会自动处理上面这些位置。

## 卸载

双击 **`uninstall.exe`**，它会：

1. 显示检测到的安装位置和占用空间；
2. 列出将要删除的内容（安装目录、桌面快捷方式、PATH 条目、`.Renviron` 行），
   逐项可以勾选；
3. 确认后删除，并报告释放了多少空间。

**不会删除**：你自己安装的 R、你的 R 库、你的测序数据和结果文件。

> 只有随程序一起装的 R（位于安装目录内的 `R\R-runtime`）才会作为可选项出现，
> 默认不勾选。

装到了非默认位置也没关系：安装器会把位置记录在
`%LOCALAPPDATA%\nanoamp.path`；即使这个记录丢了，卸载器还会去用户 PATH
指向的目录里按特征文件查找。

## 两个 exe 的命令行用法

`install.exe` 和 `uninstall.exe` 都支持无界面模式，便于批量部署或排查问题：

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

## 重要：setup 包单独就能装；两个 zip 最好解压到同一个文件夹

`install.exe` 和 `uninstall.exe` 各约 11 MB。**只解压
`nanoamp-0.1.5-windows-setup.zip` 就能装完**：`deps/pinned-R4.6.tsv` 里带着
依赖包的确切版本，安装器会自动测速选源、联网下载（约 159 MB，视网速 5–15 分钟），
`bin/minimap2.exe` 也已经在 setup 包里。

想让这一步变成"完全不联网"，就把
`nanoamp-0.1.0-windows-offline-deps.zip`（约 248 MB）**也解压到同一个目录**
（两者都以 `nanoamp-windows/` 为根），安装器看到 `_offline/` 就直接离线安装。

如果把 250 MB 依赖打进 exe，每次启动都要自解压，既慢又占空间，所以离线依赖单独成包。

`uninstall.exe` 不依赖 `_offline/`，单独拷走也能用。

## 环境要求

- **Windows 10 / 11，64 位**
- **联网可选**：只装 setup 包时需要联网下载依赖；解压了离线依赖包则全程不需要联网
- 不需要管理员权限
- 首次安装约需 1.5 GB 磁盘空间（R 约 0.5 GB + 109 个 R 包约 0.35 GB + 余量）
- **不需要 conda，不需要 WSL**

## 离线依赖从哪来（开发者）

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

# 4. 一键安装器 + 一键卸载器 exe
python release\_installer\build_exe.py
```

安装器自身的逻辑测试（不需要真正安装）：

```powershell
python release\_installer\test_installer_logic.py
python release\_installer\test_release_layout.py
python release\_installer\test_window_fit.py         # 窗口不会被内容挤出边界
python release\_installer\test_locked_file_retry.py  # 文件被占用时重试并报错
python release\_installer\test_r_version_choice.py   # 系统 R 与随包 R 的选择规则
python release\_installer\test_pinned_deps.py        # 固定版本清单、选源、minimap2 来源
```
