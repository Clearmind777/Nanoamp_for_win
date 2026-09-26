# 工作报告 29：0.1.6 发布说明与资产打包（等使用者手动发布）

- 日期：2026-09-27
- 仓库：`Nanoamp_for_win`（Windows 专用）
- 上一轮：`work_report.28.md`（安装器把 `uninstall.exe` 放进安装目录 + 去掉 ping 弹窗，
  提交 `50fb50b`）
- 本轮委托：**"整理 `RELEASE_NOTES-0.1.6.md`，并打包相应文件，完成后我将手动发布 release"**
- 本轮提交：见 §5（已推送；**Release 由使用者发布**）

---

## 1. 为什么是 0.1.6

已发布的 **v0.1.5** 附件是旧字节（setup `494886c6…`）；0.1.5 之后仓库里又积累了两轮
Windows 侧改动（GUI 与安装器）。继续用同名文件覆盖已发布附件会让下过旧包的人对不上账，
因此按 `release/README.md` 里既定的做法：**新建 tag v0.1.6**，资产改名。

核对过"改了什么"（`git diff ac29130 HEAD`，即已发布 v0.1.5 的基线到本轮）：

- `02_code/r` 下只有 `inst/configs/README.md` 与 `example_cds.json` 两个文件被改
  （它们在 0.1.5 的 tarball 里就已经是新内容，tarball 本身没变：
  `release/01_R-package/nanoamp_0.1.0.tar.gz` sha256 `03846f83…`）；
- 其余改动全部在 `02_code/PythonGUI`、`release/_installer`、文档与发布产物里。

所以 0.1.6 的定位是：**分析核心与 0.1.5 相同，只改了 Windows 界面与安装器**——
这一点写进了发布说明的第一段，避免使用者以为分析算法变了。

## 2. `release/RELEASE_NOTES-0.1.6.md`

按 0.1.5 那套结构重写（标题 / 概述 / 变化清单 / 下载哪个文件 / 安装三步 / 用法 /
功能注释 / 三种模式 / 卸载 / 验证情况 / 附件校验值 / 已知限制 / 许可证），其中
"相对 0.1.5 的变化"是 10 条，覆盖 0.1.5 之后的两轮工作：

1. 修掉"注释页卡死"（选中被重画弄丢 → 模态提示框占住窗口；重画后恢复选中、
   双击取鼠标下那一行、按钮回落到最后点过的行，并堵住两张表互相触发的循环）；
2. 注释两页只显示**本次运行**的结果（不再把上一次的 `annotation.tsv` 连同空计数画出来）；
3. 点「开始分析」清空六个结果页 + 新增「查看上次结果」（内存缓存，关窗即失效）；
4. 新增**分析名称**（留空用开始时间；只影响窗口显示，不参与分析）；
5. 不勾选"加入 PATH"也能找到 minimap2（按位置指针定位安装目录并固定
   `<安装目录>\bin\minimap2.exe`；启动时把三行路径写进日志）；
6. 离线 CDS 的「止」按目的序列长度预填（标注为预填、可改、仍校验 3 的倍数）；
7. 「变异注释」页说明缺哪一步（未开注释 / 未勾明细 / 已就绪）；
8. 可拖动分隔线、每页水平滚动条、KB/MB/GB 大小、QC「指标说明」；
9. 卸载器放入安装目录并可自删除（含"不再弹 ping 窗口"）；
10. 文档：根 README 的「输入文件契约」与中文摘要。

"验证情况"只写实测过的内容，并明确标注：本版改动在 Python 界面/安装器，
分析侧沿用 0.1.5 的结论；开发机上 `test_e2e.py` / `test_failure_reporting.py`
需要本机 R 包库、本次未复跑，而安装版端到端用的是沙箱里自带 R 与 109 个包的环境。

## 3. 打包

- `release/_build/build_assets.py`：`SETUP_VERSION` 由 `0.1.5` 改为 **`0.1.6`**
  （及文档里的示例名）；
- `release/README.md`（会进资产）：目录结构里的 setup 名、上传一节改为
  "已发布 v0.1.3/v0.1.5；**待发布 v0.1.6**（tag/标题/说明文件/内容摘要）"，
  并把"下次发版"的示例顺延到 0.1.7；同时修正一处被误替换的已发布附件名；
- `release/_build/README.md`：示例 zip 名与 `SETUP_VERSION` 的说明；
- 根 `README.md`：把 setup 包名改为 0.1.6；
- `release/RELEASE_NOTES-0.1.5.md` 保持原样（它是 0.1.5 的历史说明）。

产物：

```text
release/_build/nanoamp-0.1.6-windows-setup.zip   34,549,224 B（32.9 MiB）
  sha256 74454ce71fde20ea36ec10775376f24194dfd4738cc1496afe479646d75ce7b3
release/_build/nanoamp-0.1.0-windows-offline-deps.zip   248,027,801 B（236.5 MiB）
  sha256 2db72289a8ecef7e16ef388f8c6a8a59c1369b6c2212fcfa29d92297d9162d40（与 0.1.5 那份逐字节相同）
```

`build_assets.py` 逐条 sha256 自校验通过（setup 18 条 / 离线包 113 条与工作树一致），
`_build/SHA256SUMS.txt` 已刷新。

## 4. 验证

| 验证 | 结果 |
|---|---|
| `publish_release.py`（干跑） | 推出 `tag v0.1.6`、标题 `nanoamp 0.1.6 — Windows 版`、说明文件与两个附件都存在且 sha256 与 `SHA256SUMS.txt` 一致；因无 `GITHUB_TOKEN` 只做干跑（使用者手动发布） |
| 端到端（`tmp/verify_release_asset.ps1`，用**本版**资产） | 解压 → 静默安装（`--no-path`、非默认位置）exit 0，安装目录含 `uninstall.exe`；安装版 GUI 检查（真实窗口、七项改动 + 注释场景）exit 0；从安装目录运行 `uninstall.exe --silent`：无任何可见 cmd/ping 窗口、整个安装目录（含自身）、`config.ini`、位置指针全部清理，`%TEMP%` 无残留脚本 |
| 编码 / 一致性 | 全树 0 差异、0 未跟踪；改动文档 UTF-8 无 BOM、无替换字符 |

## 5. 提交与推送

- 入库：`release/RELEASE_NOTES-0.1.6.md`（新）、`release/_build/build_assets.py`、
  `release/_build/SHA256SUMS.txt`、`release/_build/README.md`、`release/README.md`、
  根 `README.md`、本报告与 `00_materials/README.md` 索引；
- 已推送；**Release 本身由使用者手动创建**（见下方汇报里的上传清单）。

## 6. 仍未做

1. `D:\tools\R\lib`（nanoamp + 109 个包）未恢复 → `test_e2e`、`test_failure_reporting` 未复跑；
2. 上游回灌（Linux 仓库的 L1–L13）；
3. 真机压力用例：C4 磁盘满、C9 ARM64、E2 高 DPI 截图；
4. GUI 大表虚拟化/分页（P2-2，可选）。
