# 工作报告 9：三个交付形态分离、一键安装器与面向使用者的 README

> 日期：2026-09-21
> 关联：`work_report.8.md`
> 本轮范围：把 win 仓库的 R CLI 版 / R package 版 / GUI 版完全分离；创建 install.exe；
> 重写仓库根 README.md，加入面向完全不懂生信的使用者的教程

---

## 1. 摘要

| # | 任务 | 结果 |
|---|---|---|
| 1 | 三个交付形态完全分离 | 新增 `release/`，内含 `01_R-package/`、`02_CLI/`、`03_GUI/` 三个独立目录 |
| 2 | 创建 install.exe | 完成，10.1 MB，一键安装全部组件，**免联网、免管理员权限** |
| 3 | 重写仓库根 README.md | 完成：改为中文、面向零生信背景使用者，含"傻瓜式"安装与使用教程 |

**验证结果：** install.exe 端到端安装成功（109 个依赖包 + 主程序 + CLI + GUI + 自检），
安装后的 CLI 在**干净 shell、PATH 中无仓库**的条件下跑出真实分析结果，
与命令行/图形界面基线**完全一致**。三个交付形态的布局自检 **24 项全部通过**。

---

## 2. 三个交付形态的分离

### 2.1 设计

新建 `release/` 作为**唯一要交付给使用者的目录**。整体一起发出去即可：

```text
release/
|-- install.exe          一键安装器（约 10 MB）
|-- 01_R-package/        R 包版：nanoamp_0.1.0.tar.gz + README
|-- 02_CLI/              命令行版：bin/ + README
|-- 03_GUI/              图形界面版：nanoamp.exe + README
|-- _installer/          安装器源码（Python/Tkinter + PyInstaller spec）
|-- _offline/            离线依赖：R 安装器 + 109 个 R 包 + minimap2.exe
`-- README.md            发布包总览
```

体积：`release/` 共 **274 MB**（其中 `_offline` 241 MB、两个 exe 各约 10 MB）。

### 2.2 关键约束：三者共用同一个分析核心

三个版本**不是三套程序**：

| 版本 | 它做什么 | 怎么调用核心 |
|---|---|---|
| R package 版 | 提供完整 R API | 直接 `library(nanoamp)` |
| CLI 版 | 命令行外壳 | 子进程调 `nanoamp_cli()` |
| GUI 版 | 图形外壳 | 子进程调 `nanoamp_cli()` |

所以**不存在"两个版本算出不同答案"的可能**。分离的是**交付与安装方式**，
不是算法。这一点在 `release/README.md` 和各版本 README 里都写明了。

### 2.3 各版本的独立性

- **R package 版**：一个 tarball，`install.packages(..., type="source")` 即可，
  不依赖另外两个版本。README 里写清了依赖清单与快速上手。
- **CLI 版**：自带 `nanoamp.cmd` 启动器；启动器自己找 R、自己定库路径，
  不依赖 GUI，也不要求仓库在 PATH 里。
- **GUI 版**：自带 `nanoamp.exe`；通过 `config.ini` 找到数据目录。

---

## 3. install.exe

### 3.1 它做什么

面向"完全不写代码"的使用者，只有一个按钮。执行六步：

1. 找系统里已有的 R（要求 ≥ 4.2），找不到就用 `_offline/r/` 里的安装器静默安装；
2. 从 `_offline/r-packages/` **本地仓库**安装 109 个依赖包；
3. 从 `01_R-package/` 安装 nanoamp 主程序；
4. 生成 CLI 驱动脚本 + 安装 `nanoamp.cmd`，把 bin 目录加进用户 PATH；
5. 安装 GUI 并在桌面创建快捷方式；
6. 自检（包、关键依赖、minimap2）。

**全程不联网，不需要管理员权限。**

### 3.2 安装位置与副作用

```text
%LOCALAPPDATA%\nanoamp\                安装目录
  R\lib\                               109 个 R 依赖包 + nanoamp
  app\nanoamp.exe                      图形界面
  bin\nanoamp.cmd, bin\minimap2.exe    命令行启动器 + 比对程序
  config\nanoamp_cli.R                 生成的 R 驱动脚本
  config.ini                           安装记录
%USERPROFILE%\Documents\.Renviron      R_LIBS_USER 指向上面那个库
%USERPROFILE%\Desktop\*.lnk            桌面快捷方式
用户 PATH                               追加 %LOCALAPPDATA%\nanoamp\bin
```

用 `.Renviron` 设置 `R_LIBS_USER` 而不是改 R 的 `Rprofile.site`，
好处是**不碰用户已有的 R 库**，也不需要管理员权限。

### 3.3 为什么离线依赖不打进 exe

`install.exe` 只有 **10.1 MB**，而 `_offline/` 有 **241 MB**，两者并排放置。

这是个刻意的取舍：如果把 241 MB 打进 exe，会得到一个巨大的自解压程序，
**每次启动都要解压一遍**。分开之后 exe 秒开，代价是 `install.exe`
**不能单独拷走**。这一点在 `release/README.md` 里用醒目段落写明，
并且安装器会检测到缺文件时报"安装包不完整"而不是崩溃。

### 3.4 无界面模式

同一个 exe 支持控制台模式，也是本轮测试的手段：

```bat
install.exe --silent                :: 全自动安装，日志到控制台
install.exe --silent --no-shortcut  :: 不建桌面快捷方式
install.exe --silent --no-path      :: 不改 PATH
install.exe --check                 :: 只报告状态，不做修改
```

---

## 4. 重写仓库根 README.md

### 4.1 原文的问题

1. **全英文** —— 而使用者是不懂生信的中文用户；
2. **面向开发者** —— 开篇就是仓库结构、`R CMD INSTALL`、`make` 目标；
3. **缺少最关键的东西** —— 从头到尾**没有一句"你该先做什么"**；
   使用者拿到之后不知道第一步是双击 `install.exe`；
4. **没有使用说明** —— 只有命令示例，没有"怎么选文件""结果表怎么读"；
5. **出错无处可查** —— 没有排错章节。

### 4.2 新结构

```
1. 这个软件能帮你做什么          ← 先用一段话说清价值，并解释为什么不能直接数
2. 第一次使用：三步搞定          ← 解压 → 双击 install.exe → 双击桌面图标
3. 怎么用（图解步骤）            ← ASCII 界面示意图 + 编号操作步骤
4. 怎么看结果                    ← 逐列解释结果表，并给一个真实读法示例
5. 三种版本，该用哪个            ← 选择表 + 各自 README 链接
6. 遇到问题怎么办                ← 8 个常见问题的具体处置
7. 给开发者：源码与二次开发      ← 原有技术内容保留在这一节，不再挡在前面
```

### 4.3 面向使用者的几个刻意选择

- **开头一段就说清"输入是什么、输出回答哪三个问题"**，不出现任何术语缩写
  （第一处提到 FASTQ 时标注"测序公司给你的文件"）。
- **明确警告不要放在桌面**（桌面路径通常含中文用户名），建议 `D:\nanoamp\`。
- **给出结果表的真实示例**并逐行解读：

  ```text
  排名  编号  reads 数  占比     是否一致   变异
   1    H1     142    33.3%     否       218delG
   2    H2     134    31.5%     是       .
   3    H3     114    26.8%     否       218delG;135C>T
  ```

  → 读法：这个样本里 31.5% 是目的序列，最多的一种少了一个 G……
- **解释"为什么不能直接数"**：用 2%–4% 这个实测数字说明测序错误的影响，
  避免使用者看到"完全一致只有 3%"时误判实验失败。
- **提醒低深度不可靠**：`n_reads_total` 低于 100 时比例不可信。
- **卸载方法**写清楚（删目录 + 删快捷方式 + 删 .Renviron 里那一行）。

---

## 5. 本轮发现并修复的缺陷

构建和验证过程中暴露了 8 个真实缺陷，全部已修：

| # | 缺陷 | 后果 | 修法 |
|---|---|---|---|
| 1 | `Rscript.exe CMD INSTALL` 从非控制台进程启动时崩溃（0xC0000005 访问违例） | 主程序**完全装不上** | 改用 `R.exe CMD INSTALL`（实测 rc=0） |
| 2 | Python 用控制台代码页（GBK）解码 R 的 UTF-8 输出 | 遇到中文日志直接抛 `UnicodeDecodeError` | 显式按 UTF-8 解码，`errors="replace"` |
| 3 | `configparser` 写成 `rscript = 值`（等号两侧有空格） | 批处理 `for /f "delims=="` 读到键名 `"rscript "`，永远匹配不上，CLI 找不到 R | config.ini 改为 `key=value` 无空格格式 |
| 4 | `nanoamp.cmd` 含 UTF-8 中文注释 | cmd.exe 用 OEM 代码页读 `.cmd`，中文被当成乱码命令，启动器**完全不可用** | 该文件改为**纯 ASCII**，中文说明移入 README；并加自测断言 |
| 5 | 离线安装用 `repos=` 但负载是扁平目录 | `available.packages()` 找不到索引 | 负载改为 CRAN 布局 `bin/windows/contrib/<版本>/` |
| 6 | `Rscript --version` 输出是 `Rscript (R) version 4.6.1`，正则却匹配 `R version` | 版本判定失败，会误判"R 版本过低"并重复安装 | 正则改为 `version\s+(\d+)\.(\d+)` |
| 7 | GUI 默认输出目录是仓库路径 | 安装版使用者的结果会落到 AppData 里 | 未安装时默认改为「我的文档\nanoamp 结果」 |
| 8 | GUI 依赖 PATH 找 minimap2 | 可能解析到别的副本 | 生成的 CLI 驱动里写死 `NANOAMP_MINIMAP2` |

其中 #1 和 #4 是"表面装上了、实际完全不能用"的类型，最值得记录。

### 5.1 一个方法论教训（再次）

验证 **#1** 时，我先怀疑是沙箱限制，因为从 PowerShell 直接调 `R CMD INSTALL`
能成功、从 Python 调就崩。真正定位靠的是**对比不同 R 可执行文件**：
`Rscript.exe` 崩溃（访问违例），`R.exe` 干净地返回 1 并打印
"dependencies ... are not available" —— 这条错误信息直接指向了真实原因
（环境变量/库路径），而不是继续在沙箱假设上打转。

**结论：遇到"莫名其妙的崩溃"，换一个等价的调用方式往往能换来可读的报错。**

---

## 6. 验证

### 6.1 install.exe 端到端

```text
install.exe --silent --no-shortcut --no-path
  -> 109 个依赖包安装完成（关键依赖检查 TRUE）
  -> nanoamp 主程序安装完成
  -> 命令行驱动 + nanoamp.cmd 安装完成
  -> minimap2 安装完成
  -> 图形界面安装完成
  -> 自检通过
  -> 安装成功。
```

`install.exe --check` 随后报告：

```text
nanoamp 安装目录 : C:\Users\...\AppData\Local\nanoamp  存在
R 运行环境       : D:\tools\R\R-4.6.1\bin\Rscript.exe  (4.6)
nanoamp 包      : 已安装
图形界面         : 已安装
命令行包装       : 已安装
比对程序         : 已安装
状态：可用
```

### 6.2 安装后的 CLI 在干净环境跑真实分析

把工作目录切到 `%TEMP%`、PATH 只加安装目录、清掉 `R_LIBS_USER`，
模拟使用者新开命令行的状态：

```text
nanoamp doctor
  platform: windows-x86_64
  dependence directory: NOT FOUND          <- 正常，仓库不在旁边
  Biostrings TRUE ... data.table TRUE
  minimap2  C:\Users\...\AppData\Local\nanoamp\bin\minimap2.exe (2.31-r1302)

nanoamp call --reads ... --mode A --top-n 5 --outdir ...
  rank  haplotype_id  count  proportion  is_reference  variants
  1     H1            142    0.333       FALSE         218delG
  2     H2            134    0.315       TRUE          .
  3     H3            114    0.268       FALSE         218delG;135C>T
```

与命令行、图形界面的基线**完全一致**。

### 6.3 交付形态布局自检

`release/_installer/test_release_layout.py`，**24 项全部通过**：

- 三个目录齐备，各自带 README 与可执行产物；
- R 包 tarball 存在且体积合理；
- `nanoamp.cmd` **无非 ASCII 字节**（并断言含 `rscript`、`R_LIBS_USER`）；
- `release/03_GUI/nanoamp.exe` 与 `06_GUI/dist/nanoamp.exe` 哈希一致；
- 离线依赖完整（1 个 R 安装器、109 个包、PACKAGES 索引、minimap2）；
- `release/minimap2.exe` 与仓库内副本哈希一致；
- **`release/` 下没有任何文件含本机绝对路径**（换成别人的机器会失效）；
- `install.exe --check` 报告"可用"。

### 6.4 图形界面

`install.exe` 启动后进程存活，窗口标题为「nanoamp 安装程序」。
（注：本轮两次自动截屏都拍到了前台的其他应用而不是安装窗口，
因此**安装器的视觉外观未通过截图确认**，只确认了窗口存在与标题正确。
功能验证走的是 `--silent` / `--check` 控制台路径。）

---

## 7. 已知限制

1. **未在真正没有 R、没有网络、非开发者的机器上完整走一遍** ——
   本机已有 R，安装器走的是"复用已有 R"分支；"静默安装 R"分支未实测。
2. **安装器的视觉外观未经截图确认**（见 6.4）。
3. **桌面快捷方式在本轮测试中被跳过**（用了 `--no-shortcut`），
   快捷方式创建代码未实测。
4. **PATH 修改在本轮最后几次测试中被跳过**（`--no-path`），
   但早前一次完整安装确实写入过且生效。
5. **未做卸载程序**：目前卸载靠手工删目录。
6. **install.exe 无数字签名**，首次运行可能触发 SmartScreen 提示。
7. **无批量界面**：CLI 的 `nanoamp batch` 未接进图形界面。
8. **无 GTF / CDS 功能注释**（R 核心也未实现）。

---

## 8. 下一步

1. 在一台**干净 Windows**（无 R、无网络）上跑完整流程，验证 R 静默安装分支；
2. 实机确认桌面快捷方式与 PATH 改动；
3. 增加卸载入口（安装器加 `--uninstall`，或单独出卸载程序）；
4. 给两个 exe 加图标，并考虑代码签名以消除 SmartScreen 警告；
5. 把 `nanoamp batch` 接进图形界面，支持一次选一个目录；
6. 图形界面增加"高级设置"折叠面板（`min_reads` / `min_freq` /
   `min_identity` / 线程数 / `aligner`）；
7. 继续推进 GTF / CDS 功能注释。

---

## 9. 复现命令

```powershell
# 构建三个交付形态的产物
make release                 # R 包 tarball + GUI exe 放进 release/
python release/_installer/build_installer_exe.py   # 或 make install-exe

# 自测
python release/_installer/test_installer_logic.py  # 安装器逻辑（不安装）
python release/_installer/test_release_layout.py   # 三个形态的布局自检
install.exe --check                                # 安装状态

# 实际安装（会写入 %LOCALAPPDATA% 与用户 PATH）
install.exe                                        # 图形界面
install.exe --silent                               # 控制台

# 使用者视角验证
cd $env:TEMP
$env:Path = "$env:LOCALAPPDATA\nanoamp\bin;$env:Path"
nanoamp doctor
nanoamp call --reads ... --reference ... --mode A --outdir ...
```
