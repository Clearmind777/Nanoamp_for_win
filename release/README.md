# nanoamp 发布包

这个目录是**要交付给使用者的东西**。整个 `release` 文件夹一起打包发出去即可。

## 里面有什么

```text
release/
|-- install.exe          ← 一键安装器：双击它就装好了（约 10 MB）
|-- 01_R-package/        R 包版：给要写 R 代码的同学
|-- 02_CLI/              命令行版：给要批量处理样本的同学
|-- 03_GUI/              图形界面版：给不写代码的人（最常用）
|-- _installer/          安装器源码（开发者用，使用者可忽略）
`-- _offline/            离线依赖：R 安装器 + 109 个 R 包 + minimap2
```

## 使用者怎么用

**只要做两件事：**

1. 把整个 `release` 文件夹解压到**路径不含中文和空格**的位置，例如 `D:\nanoamp\`
2. 双击 **`install.exe`**，在窗口里点「开始安装」，等 3–10 分钟

装完之后：

- 桌面出现 **「nanoamp 分析工具」** 快捷方式 → 双击打开图形界面
- 命令行里可以输入 `nanoamp doctor`、`nanoamp call ...`
- R 里可以 `library(nanoamp)`

详细的图文步骤见[仓库根目录的 README.md](../README.md)，以及各版本自己的 README。

## `install.exe` 做了什么

| 步骤 | 说明 |
|---|---|
| 1. 检查并安装 R | 先找系统里已有的 R（要求 ≥ 4.2）；找不到就用 `_offline/r/` 里的安装器静默安装 |
| 2. 安装 R 依赖包 | 从 `_offline/r-packages/` 本地仓库安装 109 个包，**全程不联网** |
| 3. 安装 nanoamp 主程序 | 从 `01_R-package/nanoamp_0.1.0.tar.gz` 安装 |
| 4. 注册 `nanoamp` 命令 | 生成 `nanoamp.cmd` 并把 `%LOCALAPPDATA%\nanoamp\bin` 加入用户 PATH |
| 5. 创建桌面快捷方式 | 指向安装好的图形界面 |
| 6. 自检 | 检查包、依赖、minimap2 是否就绪 |

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

卸载：删除 `%LOCALAPPDATA%\nanoamp`、桌面快捷方式，以及 `.Renviron` 里的那一行。

## 安装器的命令行用法

同一个 `install.exe` 也支持无界面模式，便于批量部署或排查问题：

```bat
install.exe --silent               :: 全自动安装，日志打印到控制台
install.exe --silent --no-shortcut :: 不创建桌面快捷方式
install.exe --silent --no-path     :: 不修改 PATH
install.exe --check                :: 只报告当前安装状态，不做任何修改
```

> 注意：`install.exe --silent` 需要控制台窗口才能看到输出；
> `install.exe` 不带参数时才弹图形窗口。

## 重要：不要把 `install.exe` 单独拷走

`install.exe` 只有约 10 MB，**离线依赖（约 250 MB）放在它旁边的 `_offline/` 里**。
如果把 `install.exe` 单独复制到别处运行，它会报「安装包不完整」。

这样做是刻意的：如果把 250 MB 依赖打进 exe，每次启动都要自解压，
既慢又占空间。整个 `release` 文件夹一起分发即可。

## 环境要求

- **Windows 10 / 11，64 位**
- 不需要联网
- 不需要管理员权限
- 首次安装约需 1.5 GB 磁盘空间（R 约 0.5 GB + 109 个 R 包约 0.35 GB + 余量）
- **不需要 conda，不需要 WSL**

## 重新构建这个发布包（开发者）

```powershell
# 1. R 包 tarball
R CMD build 02_code/r --no-build-vignettes
copy nanoamp_0.1.0.tar.gz release\01_R-package\

# 2. 图形界面 exe
python 06_GUI\build_exe.py
copy 06_GUI\dist\nanoamp.exe release\03_GUI\

# 3. 离线依赖（R 安装器 + R 包 + minimap2）
Rscript 03_dependence\offline-bundle\fetch_offline_bundle.R
# 然后把 dist\ 里的内容按 layout 整理进 release\_offline\

# 4. 一键安装器 exe
python release\_installer\build_installer_exe.py
```

安装器自身的逻辑测试（不需要真正安装）：

```powershell
python release\_installer\test_installer_logic.py
```
