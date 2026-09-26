# 工作报告 26：`.gitignore` 核查、发布产物重建与安装版端到端验证

- 日期：2026-09-27
- 仓库：`Nanoamp_for_win`（Windows 专用）
- 上一轮：`work_report.25.md`（GUI 三处疑点与 CDS 默认值，提交 `106068d` / `e3e08b8`）
- 本轮委托：
  1. 把 `release/nanoamp_install.log` 与 `release/nanoamp_diagnose.txt` 加进 `.gitignore`；
  2. 重建发布产物；
  3. 完成后提交并推送（**Release 暂不上传**）。
- 本轮提交：见 §5（含推送）

---

## 1. `.gitignore`：两条规则本来就在，问题在我自己的对比脚本

结论先说：**仓库不需要改动**。两个路径早已被 `release/.gitignore` 覆盖：

```text
$ git check-ignore -v -- release/nanoamp_install.log
release/.gitignore:9:*.log                              release/nanoamp_install.log
$ git check-ignore -v -- release/nanoamp_diagnose.txt
release/.gitignore:10:nanoamp_diagnose.txt              release/nanoamp_diagnose.txt
```

根 `.gitignore` 再加同名规则只会造成重复。真正出错的是我在报告 24/25 里用的
`tmp/check_tree_parity.py`：它自己写死了一张"应该忽略"的清单，**没有读 `.gitignore`**，
于是把被忽略的 `release/nanoamp_install.log` 报成"未跟踪"。已改成向 git 提问
（`git check-ignore --stdin -z`），重跑后：

```text
UNTRACKED (git would add these): 0
DIFFERING after .gitattributes normalisation: 0（提交前）
```

顺带把"`tmp/` 被脚本有意跳过导致 `tmp/test_results/README.md` 永远显示为 missing"
这条也标注清楚，不再计为问题。

## 2. 重建发布产物（未上传）

```text
nanoamp.exe        11,386,848 B   sha256 72fb5a947a7c6fa2…
                   （02_code/PythonGUI/dist/ 与 release/03_GUI/ 两份逐字节相同）

nanoamp-0.1.5-windows-setup.zip      34,532,797 B（32.9 MiB）
  sha256 52e78aeee243bc4db4488cb07a6816c5c5c3e64de05fd07a9d1ae649fc840caa
  旧值   494886c61c8814543bd204d6fb8b6ce81fe1ef12e571bf3131b885053a3b5384（已发布的 v0.1.5）

nanoamp-0.1.0-windows-offline-deps.zip   248,027,801 B（236.5 MiB）
  sha256 2db72289a8ecef7e16ef388f8c6a8a59c1369b6c2212fcfa29d92297d9162d40（未变）
```

- 步骤：`python 02_code/PythonGUI/build_exe.py` → 复制到 `release/03_GUI/nanoamp.exe`
  → `python release/_build/build_assets.py`（重建两个 zip 并重写 `_build/SHA256SUMS.txt`）。
- 打包器**逐条 sha256 自校验**：setup 18 条、离线包 113 条，全部与源文件一致
  （也就是新的 `nanoamp.exe` 确实进了资产）。
- 离线依赖包 sha256 与重建前**逐字节一致**：`_offline/` 没动，固定时间戳的确定性打包有效
  —— 这条同时证明"源材料没被改动过"。
- **打包顺序踩了一次坑，被自校验挡住**：`release/README.md`（用户拿到的说明）本身被打进
  setup 资产，而我在第一次打包之后才改它，于是 `build_assets.py --verify-only` 报
  `content mismatch for nanoamp-windows/README.md`。修法是两步：①README 里**不再写资产自身的
  sha256**（它会被自己的改动推翻），改为指向不进资产的 `release/_build/SHA256SUMS.txt`；
  ②改完文档后重新打包，得到最终的 `52e78aee…`。这正说明"内容逐条自校验"有必要。
- 固化的 exe 字符串检查（`tmp/check_frozen_strings_round26.py`，走 PYZ 里的 code 常量，
  不是裸字节搜索）：`查看上次结果`／`返回本次结果`／`本次未运行功能注释`／`未显示`／
  `已按目的序列长度预填`／`minimap2   :`／`上一次运行` 都在，且**不含**被删掉的
  ` - 纳米孔 PCR 产物分析`；同时保留上一批的 `离线 CDS（不联网）``列出转录本`
  `查看蛋白序列``恢复默认值` 等，确认没有把旧功能弄丢。

## 3. 安装版端到端验证（本次最硬的证据）

脚本：`tmp/verify_round26_install.ps1`（解压两个新资产 → 静默安装到沙箱，
`--install-dir <沙箱>\target --no-shortcut --no-path`）+ `tmp/gui_check_round26.py`
（用**真实窗口**跑分析）。

环境刻意做成"报告 ③ 的那种机器"：**不勾选加入 PATH**（`<target>\bin` 不在 PATH 里）、
**非默认安装位置**（只有 `%LOCALAPPDATA%\nanoamp.path` 指向它）、**不设** `NANOAMP_HOME`。

| 检查 | 结果 |
|---|---|
| 安装器留下的指针文件 / 安装树 | OK（`target\bin\minimap2.exe`、`target\app\nanoamp.exe`、`config.ini`、`configs\example_cds.json` 都在） |
| `find_repo_root(<install>\app)` | 返回 `<install>`（修复前会退化成 `<install>\app`） |
| `minimap2_path()` / `NANOAMP_MINIMAP2` | `<install>\bin\minimap2.exe` |
| `nanoamp doctor`（窗口给的环境） | 退出码 0；`minimap2 <install>\bin\minimap2.exe (2.31-r1302)` |
| 真实跑一次（勾选功能注释，离线 CDS 118–237） | 分析完成，12 条单倍型，`annotation.tsv` 写出，注释页 12 行 |
| **再跑一次（不勾注释，同一个输出目录）** | 分析完成；注释页 **0 行**；状态行"本次未运行功能注释（输出目录里还有上一次运行留下的 `annotation.tsv`、`variants_annotation.tsv`，未显示…）"；运行日志里**没有**空计数那行（"已注释  个转录本…"） |
| 点「查看上次结果」 | 取回上一次的 12 行，状态行带"（上一次运行 <时间> 的结果）"；再点回到本次（空） |

也就是说委托里的 ①②③ 三个现象，这次是在**装出来的程序**上按你的操作顺序复现并确认修好的，
不只是单元测试。

## 4. 其余测试

| 验证 | 结果 |
|---|---|
| GUI 自测 7 个脚本 | 通过 4 个；`test_e2e`、`test_failure_reporting`、`test_headless` 需要本机 R（`D:\tools\R` 仍为空，改动前后同样失败） |
| 安装器自测 9 个脚本 | 全部通过 |
| `test_frozen.py` | FROZEN BUILD OK（含启动新 exe 并保持运行） |
| 文档编码 / 全树编码 | UTF-8 无 BOM、无替换字符；206 个受控文本文件无乱码 |

## 5. 提交与推送

- 本轮入库文件：`release/03_GUI/nanoamp.exe`、`release/_build/SHA256SUMS.txt`、
  `release/RELEASE_NOTES-0.1.5.md`、`release/README.md`、本报告与索引；
  分两条提交：`cf26e55`（重建 + 首版资产 + 文档/报告），随后一条为**打包顺序修正**
  （README 改完 → 重新打包得到最终 `52e78aee…` → 更新 `RELEASE_NOTES` 的校验值）。
  两条都已推送（`git ls-remote origin main` == 本地 `HEAD`）。
- **Release 未上传**（按指示）。已发布的 v0.1.5 附件仍是旧字节
  （setup `494886c6…`）；仓库里重建后的 setup 同名但内容不同（`52e78aee…`），
  这一点已写进 `release/README.md` 与 `RELEASE_NOTES-0.1.5.md`：若要发布这一版，
  **请新建 tag（例如 v0.1.6）**，不要把新文件覆盖到已发布 v0.1.5 的附件上。
  `build_assets.py` 的 `SETUP_VERSION` 仍是 `0.1.5`（版本号由你定，改一行 + 重建即可）。

## 6. 仍未做

1. `D:\tools\R` 未恢复（`tmp/r_setup_and_verify.ps1` 可离线重建）；因此三个需要 R 的
   自测脚本仍未复跑。
2. 上游回灌（Linux 仓库的 L1–L13）。
3. 需真机的压力用例：C4 磁盘满、C9 ARM64、E2 高 DPI 截图。
4. GUI 大表虚拟化/分页（P2-2，可选）。
