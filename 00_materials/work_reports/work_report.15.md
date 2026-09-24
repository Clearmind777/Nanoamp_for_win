# 工作报告 15：不装离线包也能装完（固定版本 + 自动选源），并补上联网安装缺的 minimap2

- 日期：2026-09-24
- 仓库：`Nanoamp_for_win`（Windows 专用）
- 上一轮：`work_report.14.md`（安装器只选依赖包能用的那个 R；发布 v0.1.3）
- 本轮委托（用户原话）：
  1. 「install 时先查找 offline 包，没有则 R 先换源（自动选择网络最优的源），然后下载 R 包依赖」
  2. 「所有 R 包依赖都只下载固定版本」
  3. 「修改完成验证成功后，只提交和推送，不发 release」

---

## 1. 结论先说

| 问题 | 结果 |
|---|---|
| 只有 setup 包（没有 `_offline`）能不能装完？ | **能。** 现场实测：测速选中南大镜像 → 下载 109 个包（159 MB）→ 安装 → 主程序 → 配置 → 自检通过 |
| 下载的是不是**固定版本**？ | **是。** `deps/pinned-R4.6.tsv` 逐包记录 `name/version/size/md5/sha256/deps`；验收方式是读 zip 里的 `DESCRIPTION`，比对 `Package` + `Version` |
| 装出来的 109 个包版本对不对？ | 与清单**逐包比对：109/109 一致，0 个缺失、0 个版本不符** |
| 联网装完有没有比对程序？ | **本轮发现并修掉了这个洞**：原来 `minimap2.exe` 只从 `_offline/` 复制，只装 setup 包的机器装完没有比对程序。现在 setup 包里也带一份（`bin/minimap2.exe`），安装到 `<安装目录>\bin\` |
| 离线路径有没有被改坏？ | 没有。有 `_offline` 时优先用它，全离线安装，实测装完自检通过 |
| 有没有发 Release？ | **没有。** 本轮只提交 + 推送代码与文档 |

---

## 2. 联网安装这条路（本轮的主要工作）

### 2.1 两个来源，一套版本

安装器现在按"有没有 `_offline`"分两条路：

```text
_offline/ 存在  → 用本地仓库 install.packages(repos = file://…)，全程不联网
_offline/ 不存在 → 读 deps/pinned-R4.6.tsv：
                   1) 并发探测 6 个镜像的 PACKAGES.gz，算下载速度并排序
                   2) 按依赖拓扑顺序下载 109 个包
                   3) 每个包读 zip 里的 DESCRIPTION，校验 Package/Version == 清单
                   4) 一次性 install.packages()，再校验关键包能否 library()
```

机器上连 R 都没有时，R 4.6.1 运行时（91,749,976 B）也从**同一个镜像**下载，
并用清单里记录的 sha256 校验。

### 2.2 为什么验收标准是"版本"而不是"字节"

第一版实现要求下载文件与离线包的 sha256 完全一致，结果 `generics_0.1.4.zip`
直接失败：官方镜像 86,409 B，离线包 85,804 B —— **同一个版本号，镜像自己重新编译过**。
这在 CRAN/Bioconductor 的 Windows 二进制里是常态，不是例外。

所以验收改成读包内 `DESCRIPTION` 的 `Package`/`Version`：

- 版本一致 → 接受（sha256 相同则额外在日志里记一句"与离线包逐字节相同"）；
- 版本不一致 → 换下一个候选 URL（CRAN base 与 Bioconductor base 各一个）重试；
- 两个 URL 都拿不到 → 明确报错，并提示改用离线依赖包。

实测结果：109 个包里 **35 个与离线包逐字节相同，74 个是镜像重新编译的同版本文件**。
另外单独核对过：**109 个固定版本目前全部仍在镜像上**（`same=109 diff=0 absent=0`）。

### 2.3 选源

6 个镜像按 `PACKAGES.gz`（索引文件，小且一定存在）的下载速度排序，实测：

| 镜像 | 速度 |
|---|---|
| 南大 NJU | 2.75 MB/s ← 选中 |
| 清华 TUNA | 1.68 MB/s |
| 中科大 USTC | 1.46 MB/s |
| CRAN 官方 | 0.81 MB/s |
| 阿里云 | 0.34 MB/s |
| 北外 BFSU | 探测失败（该镜像当时不可达） |

> 踩过的坑：第一版探测用的是"清单里最小的那个包"。结果 6 个镜像全部报"不可用"——
> 因为最小的是索引类小包，在部分镜像上 404/403。改成探测 `PACKAGES.gz` 之后正常。
> **教训：测速要用"必然会存在"的资源，不能用"我们以为存在"的资源。**

### 2.4 现场日志（节选）

```text
离线依赖包   : 未找到
                将先测速选源，再按固定版本下载 R 依赖包（109 个，清单 pinned-R4.6.tsv）
正在测试 6 个镜像的下载速度…
选用镜像：南大 NJU
开始下载 109 个依赖包（固定版本，共约 159 MB）…
下载完成：109 个包，版本全部与固定清单一致
        （其中 35 个与离线包逐字节相同，74 个是镜像重新编译的同版本文件）
R 依赖包安装完成（联网下载，版本与离线包一致）
nanoamp 安装完成
自检通过
安装成功。
```

装完后逐包核对安装目录里的 `DESCRIPTION`：

```text
pinned: 109
installed-dir-missing: 0 []
version-mismatch: 0 []
OK
```

---

## 3. 本轮发现的第二个洞：联网装完没有 minimap2

### 3.1 怎么发现的

联网安装的自检输出里，`minimap2` 那一行显示的是

```text
minimap2     E:\...\Nanoamp_for_win\03_dependence\windows-x86_64\bin\minimap2.exe
```

—— 指向**仓库源码目录**，而安装目录的 `bin\` 里只有 `nanoamp.cmd`。

原因：复制比对程序那一步写的是 `mm = self.ctx.offline / "minimap2.exe"`，
`_offline` 不存在时这一整段被跳过。R 包随后靠"从当前目录往上找 `03_dependence`"
找到了仓库里的那份 —— 在开发机上看起来一切正常，**在用户机器上就是
`nanoamp doctor` 显示 `NOT FOUND`、比对步骤直接报错**。

### 3.2 怎么修的

1. `build_assets.py` 把 `_offline/minimap2.exe` **以 `bin/minimap2.exe` 的名字**
   打进 setup 资产（`SETUP_EXTRA` 映射），树里仍然只有一份 1.3 MB 的二进制；
2. 安装器按顺序找：`_offline/minimap2.exe` → `bin/minimap2.exe` → 源码目录的
   `03_dependence/...`（只有从仓库里跑 `release\install.exe` 时才会命中第三个）；
3. 都找不到时**预检查直接报错**，而不是"装完看起来成功、比对时才炸"；
4. GUI 侧也补了一刀：`r_runner._env()` 现在直接设
   `NANOAMP_MINIMAP2=<安装目录>\bin\minimap2.exe`。原来只能靠 PATH，
   而用户 PATH 是安装时改的，**已经开着的资源管理器不一定会刷新**，
   于是"刚装完就打开 GUI 分析"可能失败。现在不依赖 PATH 了。

> 这一条也顺带解释了为什么之前没发现：离线安装的机器上 `_offline/minimap2.exe`
> 一直在，`bin\minimap2.exe` 也就一直在。

---

## 4. 验证

### 4.1 联网安装（只用 setup 包，沙箱）

在 `tmp/online_sandbox`（重定向 `USERPROFILE`/`LOCALAPPDATA`/`APPDATA`）里，
从**新构建的 setup 资产**解压出来，只跑 `install.exe --silent --no-shortcut --no-path`：

| 检查项 | 结果 |
|---|---|
| 选源 | 南大 NJU |
| 下载 | 109/109，版本全部与清单一致 |
| 安装依赖 | 109 个包安装成功 |
| 主程序 | `* DONE (nanoamp)` |
| 比对程序 | `已安装比对程序 minimap2 -> <沙箱>\target\bin\minimap2.exe` |
| 自检 | `自检通过` |
| 安装结果 | `安装成功。` |
| 版本对账 | 109/109 与 `pinned-R4.6.tsv` 一致 |

### 4.2 离线安装（带 `_offline`，沙箱）

见 §5 复现命令；同样装完自检通过，且**没有联网**（`repos = file://…`）。

### 4.3 单元/布局测试

见 `Makefile` 的 `release-test`：

```text
test_installer_logic.py        安装器逻辑（预检查、路径发现）
test_release_layout.py         交付形态布局 + setup 资产里的 bin/minimap2.exe 与 deps 清单
test_window_fit.py             两个窗口不会被内容挤出边界
test_locked_file_retry.py      文件被占用时重试并报错
test_r_version_choice.py       系统 R / 随包 R 的选择规则
test_pinned_deps.py            清单本身、依赖拓扑序、选源规则、URL 形状、
                               zip 内 Version 识别、minimap2 三种来源、
                               清单与离线包逐字节一致
```

`test_pinned_deps.py` 本轮新增 6 项断言，专门盯 minimap2 的来源与
"树里不重复存二进制"这两件事。

---

## 5. 怎么复现

```powershell
# 1) 重建清单（离线包内容变了才需要）
python release\deps\build_pinned_manifest.py

# 2) 重新打包两个资产（会逐条自校验并重写 SHA256SUMS.txt）
python release\build_assets.py

# 3) 自测
python release\_installer\test_pinned_deps.py
python release\_installer\test_release_layout.py
python release\_installer\test_r_version_choice.py
```

联网安装（沙箱，不碰真实系统）：

```powershell
Expand-Archive release\nanoamp-0.1.5-windows-setup.zip tmp\online_test -Force
$sandbox = "$PWD\tmp\online_sandbox"
$env:USERPROFILE = "$sandbox\profile"; $env:LOCALAPPDATA = "$sandbox\localappdata"
tmp\online_test\nanoamp-windows\install.exe --silent --install-dir "$sandbox\target" --no-shortcut --no-path
```

离线安装：再把 `nanoamp-0.1.0-windows-offline-deps.zip` 解压到同一目录（出现 `_offline\`）
后跑同样的命令。

---

## 6. 本轮改动的文件

| 文件 | 改动 |
|---|---|
| `release/_installer/install_nanoamp.py` | 新增 `BIN_DIR`、`Context.minimap2_exe`；预检查要求比对程序存在；复制比对程序改为多来源 |
| `release/build_assets.py` | `SETUP_VERSION=0.1.5`；新增 `SETUP_EXTRA` 把 `_offline/minimap2.exe` 打成 `bin/minimap2.exe`；`iter_files/verify_zip` 支持改名条目 |
| `release/_installer/build_exe.py` | 负载自检改为反映"离线包可选"：缺 `_offline` 只提示，缺清单/比对程序才告警 |
| `02_code/PythonGUI/nanoamp_gui/r_runner.py` | 运行 R 时设 `NANOAMP_MINIMAP2=<home>\bin\minimap2.exe`，不再依赖 PATH 刷新 |
| `release/_installer/test_pinned_deps.py` | 新增比对程序来源、资产映射的断言 |
| `release/_installer/test_release_layout.py` | 新增"setup 资产里含 bin/minimap2.exe 与 deps 清单"的检查 |
| `release/README.md` | 资产名 0.1.5、目录树含 `bin/`、安装步骤表、发布状态（0.1.4/0.1.5 未发布） |
| `README.md` | 安装说明、排错表、"安装包不完整"的判定（`_offline` 已可选）、仓库结构 |
| `00_materials/tutorial.md` | §0.5 与安装表：只下 setup 也能装；报错自查补两条 |
| `release/install.exe`、`release/03_GUI/nanoamp.exe` | 重新构建（含上述修复） |
| `release/SHA256SUMS.txt` | 重新生成 |

---

## 7. 遗留与注意

1. **v0.1.4 与 v0.1.5 都没有发布**（本轮按要求只提交推送）。真要发的时候：
   `gh release create v0.1.5 release\nanoamp-0.1.5-windows-setup.zip --notes-file …`，
   离线依赖包仍不需要重发（内容自 0.1.0 起未变，已在 v0.1.2 附件里）。
2. **不要删 v0.1.2 的 Release**：v0.1.3 的发布说明链接指向它的离线依赖附件。
3. 镜像上的固定版本不是永久保证。哪天下架了，安装器会明确报错并建议改用离线包；
   那时要么更新清单（连同离线包一起换版本），要么就继续发离线包。
4. 248 MB 的离线依赖包**不能进 Git**（超过 GitHub 单文件 100 MiB），
   仓库里只提交 `SHA256SUMS.txt` 作为对账凭据。
