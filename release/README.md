# nanoamp 发布包

这个目录里**两个 zip 就是可以直接上传到 GitHub Release 的资产**，其余是它们的源材料。

## 要发布的两个资产

```text
release/
|-- nanoamp-0.1.3-windows-setup.zip          ← 上传这个（约 33 MB）
|-- nanoamp-0.1.0-windows-offline-deps.zip   ← 和上面一起上传（约 248 MB）
|-- SHA256SUMS.txt      ← 两个 zip 的 sha256，随仓库提交，便于对账
|-- build_assets.py     ← 重新生成上面两个 zip（内容逐条自校验）
|
|-- install.exe          ← setup zip 的源材料（约 11 MB）
|-- uninstall.exe        ← setup zip 的源材料
|-- 01_R-package/         R 包版：给要写 R 代码的同学
|-- 02_CLI/               命令行版：给要批量处理样本的同学
|-- 03_GUI/               图形界面版：给不写代码的人（最常用）
|-- _installer/           安装器源码（开发者用，使用者可忽略）
|-- diagnose_install_env.* 装不上时用来采环境信息
`-- _offline/             offline-deps zip 的源材料：R 安装器 + 109 个 R 包 + minimap2
```

两个 zip 的内部结构**共用一个根目录** `nanoamp-windows/`：

```text
nanoamp-windows/            ← 两个 zip 都解压到同一个地方
|-- install.exe  uninstall.exe
|-- 01_R-package/  02_CLI/  03_GUI/  _installer/  diagnose_install_env.*
`-- _offline/               ← 来自 nanoamp-0.1.0-windows-offline-deps.zip
```

> 两个 zip 合计约 280 MB。**248 MB 的离线依赖包超过 GitHub 单文件 100 MiB 的硬限制，
> 因此 zip 不进 Git**（`.gitignore` 已排除）；仓库里只提交 `SHA256SUMS.txt`，
> 任何时候都能用它确认"这个资产是不是这个版本构建出来的"。

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

# 4. 打包成两个资产 zip，并重写 SHA256SUMS.txt
python release\build_assets.py

# 5. 只校验（不重建）：解压后每条内容与源材料逐字节比对
python release\build_assets.py --verify-only
```

`build_assets.py` 用固定时间戳写 zip，所以同样的源材料给出同样的字节；
它会把产物解压回来、逐条与源文件比 sha256，不一致就直接报错退出。

### 与本仓库已发布资产对账

```powershell
python release\build_assets.py --compare-published <下载的 setup.zip> <下载的 offline-deps.zip>
```

会列出条目差异与 CRC 不一致的文件（离线依赖包 113 个文件里 112 个与 v0.1.2 的
资产完全一致，唯一差异是 `PACKAGES` 索引的行尾：发布版是 CRLF，仓库里是 LF，
内容逐行相同）。

## 上传

```powershell
gh release create v0.1.3 `
  release\nanoamp-0.1.3-windows-setup.zip `
  release\nanoamp-0.1.0-windows-offline-deps.zip `
  --title "nanoamp 0.1.3 — Windows 版" --notes-file <说明.md>
```

或在 GitHub 网页上对某个 tag 上传这两个文件。名字不要改：使用者按
`nanoamp-<版本>-windows-setup.zip` 找安装包，`nanoamp-0.1.0-windows-offline-deps.zip`
的版本号保持 0.1.0（离线依赖本身没有变化）。

## 使用者怎么用

**只要做两件事：**

1. 把整个 `release` 文件夹解压到**路径不含中文和空格**的位置，例如 `D:\nanoamp\`
2. 双击 **`install.exe`**，在窗口里点「开始安装」，等 3–10 分钟

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
| 1. 检查并安装 R | 先找系统里已有的 R（要求 ≥ 4.2）；找不到就用 `_offline/r/` 里的安装器静默安装 |
| 2. 安装 R 依赖包 | 从 `_offline/r-packages/` 本地仓库安装 109 个包，**全程不联网** |
| 3. 安装 nanoamp 主程序 | 从 `01_R-package/nanoamp_0.1.0.tar.gz` 安装 |
| 4. 注册 `nanoamp` 命令 | 生成 `nanoamp.cmd` 并把 `<安装目录>\bin` 加入用户 PATH（可取消） |
| 5. 创建桌面快捷方式 | 指向安装好的图形界面（可取消） |
| 6. 自检 | 检查包、依赖、minimap2 是否就绪 |

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

## 重要：两个 zip 要解压到同一个文件夹

`install.exe` 和 `uninstall.exe` 各约 11 MB，**离线依赖（约 250 MB）在
`nanoamp-0.1.0-windows-offline-deps.zip` 里**。使用者要把
`nanoamp-0.1.3-windows-setup.zip` 与 `nanoamp-0.1.0-windows-offline-deps.zip`
**解压到同一个目录**（两者都以 `nanoamp-windows/` 为根），再双击里面的
`install.exe`。只解压 setup 包就运行，`install.exe` 会报「安装包不完整」。

这样做是刻意的：如果把 250 MB 依赖打进 exe，每次启动都要自解压，既慢又占空间。

`uninstall.exe` 不依赖 `_offline/`，单独拷走也能用。

## 环境要求

- **Windows 10 / 11，64 位**
- 不需要联网
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
```
