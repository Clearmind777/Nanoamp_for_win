# 工作报告 10：安装位置可选、快捷方式可选、一键卸载器

> 日期：2026-09-21
> 关联：`work_report.9.md`
> 本轮范围：`install.exe` 增加「修改安装位置」；桌面快捷方式改为可选（默认勾选）；
> 新增 `uninstall.exe`

---

## 1. 摘要

| # | 需求 | 结果 |
|---|---|---|
| 1 | 允许推送 | 三个提交已推送，远端与本地一致 |
| 2 | `install.exe` 增加「修改安装位置」 | 完成：窗口顶部可改路径，实时显示目标磁盘剩余空间 |
| 3 | 快捷方式改为可选（默认勾选） | 完成：桌面快捷方式与 PATH 各有独立勾选框，默认都勾选 |
| 4 | 创建 `uninstall.exe` | 完成：10.0 MB，GUI + 控制台模式，干净卸载 |

**验证：** 完整「安装 → 自检 → 卸载」往返通过。安装写入的全部内容
（安装目录、桌面快捷方式、PATH 条目、`.Renviron` 行、位置记录）
都被卸载器清理干净，**无残留**。

---

## 2. 安装位置可选

### 2.1 界面

安装窗口顶部新增「安装位置」区：

```text
┌─ 安装位置 ──────────────────────────────────────────────┐
│  C:\Users\xxx\AppData\Local\nanoamp   [修改…] [恢复默认] │
│  默认装在当前用户目录下，不需要管理员权限。也可以改到      │
│  D:\nanoamp 这类位置（路径请避免中文和空格）。            │
│  将安装到：D:\nanoamp    该磁盘剩余 187.6 GB             │
└─────────────────────────────────────────────────────────┘
┌─ 选项 ──────────────────────────────────────────────────┐
│  ☑ 在桌面创建快捷方式（推荐）                            │
│  ☑ 把 nanoamp 命令加入用户 PATH（推荐）                  │
└─────────────────────────────────────────────────────────┘
```

- 「修改…」打开目录选择器；如果选中的目录名不是 `nanoamp`，
  会自动在其下建一个 `nanoamp` 子目录，避免把文件散落到用户选中的目录里。
- 实时显示目标磁盘剩余空间，不足 1.5 GB 时变红提示。
- 路径含非法字符（`<>:"|?*`）时拒绝并给出中文提示。
- 如果检测到**另一个位置**已有安装，会先询问是否继续。

### 2.2 装到非默认位置后怎么还能被找到

这是本轮最关键的设计点。有三条路径，互为兜底：

1. **相对自身定位**：`nanoamp.cmd` 用 `%~dp0..` 推断安装根目录，
   **不再硬编码** `%LOCALAPPDATA%\nanoamp`。这是被迫修掉的一个真 bug ——
   原来的启动器写死了默认路径，装到 `D:\nanoamp_test` 后 CLI 直接报
   「Rscript.exe was not found」。
2. **位置记录**：安装器把安装根目录写到
   `%LOCALAPPDATA%\nanoamp.path`，卸载器优先读它。
3. **特征文件扫描**：如果记录也丢了，卸载器会去**用户 PATH 指向的目录**
   里找 `nanoamp.cmd`，再检查同级/上级是否有
   `config\nanoamp_cli.R`、`R\lib\nanoamp`、`app\nanoamp.exe` 这些特征文件。

第 3 条只在确认特征文件存在时才认定，宁可找不到也不猜错目录 ——
因为卸载器会删目录。

---

## 3. 快捷方式与 PATH 可选

两个独立的勾选框，默认都勾选：

| 选项 | 取消后的后果 |
|---|---|
| 在桌面创建快捷方式 | 不建 `.lnk`；安装完成提示框会改为告知 `app\nanoamp.exe` 的完整路径 |
| 把 nanoamp 命令加入用户 PATH | 不改注册表；提示框会改为告知用完整路径调用 `nanoamp.cmd` |

安装完成后的提示框会根据这两项**动态调整文案**，不再出现"双击桌面图标"
却根本没有图标的矛盾提示。

控制台模式对应 `--no-shortcut` / `--no-path`。

---

## 4. uninstall.exe

### 4.1 行为

双击后显示：检测到的安装位置、占用空间、将要删除的清单（可逐项勾选）、
以及**不会删除**的内容。确认后执行并报告释放了多少空间。

删除的内容：

| 项目 | 说明 |
|---|---|
| 安装目录 | 整个递归删除，含 109 个 R 包 |
| 桌面快捷方式 | 存在才显示该选项 |
| 用户 PATH 条目 | 精确匹配 `<安装根>\bin` 后移除 |
| `.Renviron` 的 `R_LIBS_USER` 行 | 移除后若文件为空则删除该文件 |
| 位置记录 `%LOCALAPPDATA%\nanoamp.path` | |
| 随程序安装的 R | **可选，默认不勾选**；且仅当它位于安装目录内才提供 |

**不删除**：用户自己安装的 R、用户的 R 库、测序数据与结果文件。

### 4.2 安全护栏

卸载器会删目录，所以做了几层保护：

1. **禁止删除系统目录**：`C:\Windows`、系统盘根、`Program Files`、
   用户主目录、`LOCALAPPDATA`、`APPDATA` 本身都在禁止清单里。
2. **必须有特征文件**：目标目录里必须存在 `R\lib\nanoamp`、
   `app\nanoamp.exe`、`bin\nanoamp.cmd`、`config.ini` 之一，
   否则拒绝删除并说明原因。
3. **只删自己的 R**：只有当 R 运行时确实位于安装目录**之下**才会删。
4. **重试与提示**：文件被占用时重试 4 次，仍失败则明确提示
   "请先关闭正在运行的 nanoamp 窗口"。

### 4.3 控制台模式

```bat
uninstall.exe --dry-run                 :: 只报告会删什么，不真删
uninstall.exe --silent                  :: 全自动卸载
uninstall.exe --silent --keep-runtime   :: 保留随程序安装的 R
```

---

## 5. 本轮发现并修复的 5 个缺陷

| # | 缺陷 | 后果 | 修法 |
|---|---|---|---|
| 1 | `config.ini` 的 `home=` 写成了**负载目录**而非安装根目录（用了 `ctx.root` 而不是 `ctx.install_root`） | `--check` 和卸载器都指向 release 目录，报告"该目录下没有已安装的 nanoamp" | 改写入 `install_root` |
| 2 | `nanoamp.cmd` 硬编码 `%LOCALAPPDATA%\nanoamp` | 装到自定义位置后 CLI 完全不可用 | 改用 `%~dp0..` 从自身位置推断 |
| 3 | 快捷方式用的 `.vbs` 以 **UTF-8** 写出，而 cscript 按 ANSI 代码页读取 | 中文快捷方式名变成 `nanoamp ????.lnk`，`Save()` 失败、快捷方式根本没创建 | 改为 **UTF-16LE + BOM**（wscript 自己的编码） |
| 4 | 自检不带 `NANOAMP_MINIMAP2` | 在工作目录位于源码仓库时，`nanoamp_tool_path()` 会向上找到**仓库里的** minimap2.exe，自检结果误导 | 自检也显式设置该变量 |
| 5 | 离线包 `PACKAGES` 索引被上一轮用 PowerShell 重写坏（`Package` 列重复、`File` 列丢失） | R 报 `subscript out of bounds`，**依赖装不上** | 用 R 的 `write_PACKAGES()` 重新生成，并断言"可见包数 == zip 数" |

缺陷 3 与缺陷 5 尤其值得记：

- **3** 是"看起来做了、其实没做"：代码走完了 `sc.Save`，但退出码非 0 被忽略，
  函数返回 `False` 也没人看。现在会检查返回码与文件是否存在，并把 cscript
  的报错带回日志。
- **5** 是我自己上一轮引入的：用 PowerShell 对 UTF-8 文本做字符串替换，
  把 DCF 格式写坏了。**教训：格式敏感的文本文件（如 R 的 PACKAGES）
  只能用对应的工具（R）生成，不要用通用文本替换。**

---

## 6. 验证

### 6.1 完整往返

```
1) install.exe --silent                     退出码 0，耗时约 54 秒
   -> 109 个依赖包 / nanoamp 包 / CLI / GUI / minimap2 / 快捷方式 / 自检
   -> 自检: minimap2 = C:\...\nanoamp\bin\minimap2.exe   （已指向安装副本）

2) install.exe --check
   状态：可用
   安装目录 / R / 包 / 图形界面 / 命令行包装 / 比对程序 / 桌面快捷方式 全部"已安装/已创建"

3) 已安装 CLI，在 %TEMP% 下、PATH 只加安装目录、无 R_LIBS_USER
   -> minimap2  C:\Users\...\nanoamp\bin\minimap2.exe (2.31-r1302)

4) uninstall.exe --dry-run
   安装目录 (355 MB) / 删除目录 True / 快捷方式 True / PATH True / .Renviron True

5) uninstall.exe --silent                   退出码 0
   安装目录已删除
   已删除 C:\Users\...\Desktop\nanoamp 分析工具.lnk
   已从用户 PATH 移除 C:\Users\...\nanoamp\bin
   已删除空的 C:\Users\...\Documents\.Renviron
   已清理安装位置记录
   释放约 355 MB

6) 卸载后核对
   安装目录 False / 快捷方式 False / 指针文件 False / .Renviron False / PATH 残留 False
```

### 6.2 自定义位置与本地化

- 安装到 `D:\nanoamp_test`：依赖、主程序、GUI、自检全部通过；
  启动器从自身位置正确定位；卸载器通过位置记录找到它并干净删除。
- 桌面快捷方式名为 `nanoamp 分析工具.lnk`，指向
  `...\nanoamp\app\nanoamp.exe`，工作目录正确。

### 6.3 自测套件

- `test_installer_logic.py`：INSTALLER LOGIC OK
- `test_release_layout.py`：**ALL DELIVERABLE CHECKS PASSED**
  （含"`install.spec` 使用 onedir、未引用 `_offline`"、
  "两个 exe 的控制台模式都有输出"、"release/ 无本机绝对路径"）

---

## 7. 已知限制

1. **仍未在真正没有 R、没有网络的干净机器上完整验证** ——
   本机有 R，走的是"复用已有 R"分支。
2. **安装器/卸载器的图形外观未截图确认**（两次自动截屏都拍到了前台其他应用）。
   功能验证走控制台模式。
3. **卸载器的"文件被占用时重试"路径未实测**（测试时没有占用）。
4. **`install.exe` 与 `uninstall.exe` 无数字签名**，首次运行可能触发 SmartScreen。
5. **未做"修复安装"**：装坏了只能重新运行 `install.exe`。
6. **卸载不清理用户在 `%TEMP%` 下留下的输出**（本来也不该清理）。
7. **无批量界面**、**无 GTF/CDS 注释**（与上一轮相同）。

---

## 8. 下一步

1. 在干净 Windows 上验证：无 R → R 静默安装分支；无网络 → 全离线；
   以及快捷方式与 PATH 的实际写入。
2. 给两个 exe 加图标，考虑代码签名。
3. `install.exe` 增加"修复安装"入口。
4. 把 `nanoamp batch` 接进图形界面。
5. 继续推进 GTF / CDS 功能注释。

---

## 9. 复现命令

```powershell
# 构建两个 exe
python release/_installer/build_exe.py

# 自测（不安装）
python release/_installer/test_installer_logic.py
python release/_installer/test_release_layout.py

# 安装/卸载
release\install.exe                                   # 图形界面（可改位置、勾选项）
release\install.exe --silent --install-dir D:\nanoamp # 控制台
release\install.exe --check
release\uninstall.exe --dry-run
release\uninstall.exe --silent
```
