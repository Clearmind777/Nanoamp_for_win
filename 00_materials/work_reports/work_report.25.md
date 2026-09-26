# 工作报告 25：GUI 三处疑点（旧注释残留、结果页刷新、安装后找不到 minimap2）与 CDS 默认值

- 日期：2026-09-27
- 仓库：`Nanoamp_for_win`（Windows 专用）
- 上一轮：`work_report.24.md`（README 输入文件契约、`tmp/` 清理、R 环境丢失，提交 `06b1188`）
- 本轮委托：
  1. 三个 GUI 疑点算不算漏洞：①关掉功能注释后日志仍打印"已注释 个转录本…"；
     ②关掉注释后再跑比对，注释两页仍是上一次的结果（并希望"点开始分析后每页初始化，
     上一次的结果先缓存，直到程序退出"）；③`install.exe` 不勾选"添加 PATH"时，
     `nanoamp.exe` 似乎找不到 `minimap2.exe`；
  2. GUI 里功能注释的 CDS「止」能否设置默认值；
  3. **本次只提交，不推送**。
- 本轮提交：`106068d`（代码 + 测试 + 文档，本地提交，未推送）

---

## 1. 疑点 ① 与 ②：同一个真实漏洞（旧注释文件被当成新结果）

### 现象与成因

R **从不删除**上一次运行留下的 `annotation.tsv` / `variants_annotation.tsv`
（只有产出时才覆盖写），而窗口的 `_load_annotation()` 原先是"看文件在不在"来决定显示什么：

```python
if not requested and not ann_path.is_file():   # 旧文件在，于是这条不成立
    ... 未运行功能注释 ...
```

于是：开着注释跑一次 → 关掉注释再跑一次到**同一个输出目录** → `qc.tsv` 里
`annotation_enabled=FALSE`（本次确实没注释），但目录里旧的两个注释文件还在，
窗口就把它们画了出来。计数为空也是同一个原因：本次的 `qc.tsv` 没有
`n_transcripts_annotated` 等指标，所以拼出 `已注释  个转录本、  个单倍型（来源： ）。共 12 行后果。`
——与你看到的那行完全一致。

**结论：是漏洞，而且是①和②同一个漏洞。**

### 改法

1. `_load_annotation()` 改为以**本次运行的记录**为准：`annotation_enabled=TRUE` 才读注释文件；
   没开注释时明确写"本次未运行功能注释（输出目录里还有上一次运行留下的
   `annotation.tsv`、`variants_annotation.tsv`，未显示；点「查看上次结果」可看上次内容）"，
   并把这一行写进运行日志。"只给一个输出目录、里面没有 `qc.tsv`"的情况仍按原样读文件。
2. 该方法**每条返回路径**都会把 `annotation_records` / `variant_records` /
   蛋白视图索引 / 单倍型筛选一起清空，避免表格空了而下游（蛋白窗口、筛选标签）
   还拿着上一次的数据。

## 2. 疑点 ② 的第二部分：每页初始化 + 上一次结果缓存到退出

- `_clear_results()` 现在把**六个结果页**完整初始化：四张表的行、QC 文本、序列框、
  `haplotypes.fasta` 缓存、已加载的注释记录、两个筛选标签（此前会留下
  "仅显示 H2（1 / 2 行）"这类旧文案）、两个注释页状态行。
  **「运行日志」不清空** —— 它是本次会话的历史，不是某一次运行的结果。
- `_keep_previous_results()` 在清空**之前**把当前页面快照进内存
  （行、QC 文本、序列、注释记录、筛选条件、fasta 缓存、两个状态行、时间与输出目录）；
  `_remember_current_view()` 在每次运行结束时记录"本次"的快照。
- 新增按钮 **「查看上次结果」**（动作行）：在"上一次"和"本次"之间切换，
  看上一次时状态行会标注"（上一次运行 <时间> 的结果）"并把「打开输出目录」
  指向那次的目录；按钮文字随之变成「返回本次结果」。快照只在内存里，关窗即消失。
  （运行中若正在看上一次，开始新分析不会用"上一次"覆盖缓存。）

## 3. 疑点 ③：确实是漏洞，但锅不在安装器的 PATH 选项

安装器**无论是否勾选"加入 PATH"，都会**把比对程序复制到
`<安装目录>\bin\minimap2.exe`（`_configure_cli()` 末尾无条件执行）。真正的问题在窗口：
`app.find_repo_root()` 只认**默认安装位置**（`%LOCALAPPDATA%\nanoamp\config.ini`），
完全没读安装器为非默认位置写的指针文件 `%LOCALAPPDATA%\nanoamp.path`。

于是非默认安装时：

| 步骤 | 修复前 | 修复后 |
|---|---|---|
| 工作目录 | 退化成 `...\nanoamp-custom\app`（exe 所在目录，向上找不到仓库标记） | `...\nanoamp-custom` |
| `<工作目录>\bin\minimap2.exe` | 不存在 → **不设置** `NANOAMP_MINIMAP2` | 存在 → 固定给 R |
| R 侧结果 | 退回 `PATH` 查找 → 未勾选 PATH 时"External tool 'minimap2' not found" | 直接用安装目录里的那一份 |

实测（`tmp/evidence_minimap2_root.py`，构造"非默认安装 + 指针文件 + 默认位置没有
config.ini"的目录树）：

```text
before the fix  repo_root = ...\nanoamp-custom\app      bin/minimap2.exe found? False
                -> NANOAMP_MINIMAP2 NOT pinned (R falls back to PATH)
after the fix   repo_root = ...\nanoamp-custom          bin/minimap2.exe found? True
```

这也解释了为什么"勾选 PATH 就正常"：R 在 PATH 里找到了那份，绕过了窗口的这个缺陷。

改法：

1. `find_repo_root()` 改用**和定位 R 相同的解析器**（`r_runner._configured_paths()`）：
   `NANOAMP_HOME` → 指针文件指向的安装目录 → 默认位置的 `config.ini` → 从 exe 向上找仓库标记；
2. `NanoampRunner.minimap2_path()` 按 **R 自己的优先级**解析：
   `NANOAMP_MINIMAP2` → `<工作目录>\bin` → `<安装目录>\bin` → 仓库的
   `03_dependence\<平台>\bin` → `PATH`（最后一级）；命中即通过 `NANOAMP_MINIMAP2` 交给 R。
   顺带修掉一个连带问题：在源码仓库里直接跑时，窗口原先会报"未找到 minimap2"，
   而分析其实能找到仓库自带的那份 —— 现在两级一致；
3. 窗口启动时把 **仓库根目录 / Rscript / minimap2** 三行写进运行日志，
   「复制诊断信息」也带上这三行，以后同类问题一眼可判。

## 4. CDS「止」的默认值（委托 2）

**能，已实现**：选好**目的序列**后，「止」按该 FASTA 第一条序列的长度预填
（只读第一条、读到第二个 `>` 即停，不会读完整条基因组），提示行补一句
"（「止」是按目的序列长度预填的，请按实际 CDS 修改）"，日志也记一行。

三条约束保证它不会变成"沉默的错误默认值"：

- **明确标注**是预填值，不是真实 CDS 终点；
- 长度不是 3 的倍数时，原有校验照旧拒绝运行并说明要删几个碱基；
- **用户一旦改过该值，窗口不再覆盖它**（只有窗口自己写的值才会随目的序列更新；
  参考长度变了下一次仍会自动更新）。

如果你更希望"记住上次填过的坐标"或"从选中的自定义 JSON 里读坐标"，都可以替换成那种默认值，
说一声即可（当前实现选的是"窗口自己算得出来、且不需要历史状态"的那一个）。

## 5. 验证

| 验证 | 结果 |
|---|---|
| `test_annotation_gui.py` | 全通过。新增 **6j**（旧注释文件不显示、被跳过的注释页保持空）、**6k**（开始分析清空六个页、日志保留、上次结果可切回并带标注、切回本次）、**6l**（预填出现 / 跟随新参考 / 让位于用户输入），**7** 追加"动作行按钮不越界"两条（1040 与 880 宽都在窗口内） |
| `test_bundled_r_lookup.py` | 全通过。新增"安装目录 + 比对程序"一节：默认安装、非默认安装（指针文件）、只有 PATH、源码仓库里的 `03_dependence`、显式 `NANOAMP_MINIMAP2` 五种情形 |
| 其余 GUI 自测 | `test_cancel_analysis.py`、`test_frozen.py` 通过；`test_e2e.py`、`test_failure_reporting.py`、`test_headless.py` **需要 R**，本机 `D:\tools\R` 为空（见报告 24 §2），三者在改动前就同样失败 |
| 安装器自测（9 个脚本） | 全部通过（本轮未改安装器） |
| 窗口示意图 | 由 `tmp/gen_window_diagram.py` 重新生成（57→68 列，容纳新按钮），`tmp/audit_diagrams.py` 审计 **0 处错位** |
| 文档检查 | 本轮改动文档均为 UTF-8 无 BOM、无替换字符、代码围栏配平 |
| 全树编码扫描 | 新增 `tmp/check_mojibake.py`：205 个受控文本文件全部干净 |
| 实测证据 | `tmp/evidence_minimap2_root.py` 打印修复前后的 `repo_root` 与 `bin\minimap2.exe` 命中情况（见 §3） |

## 6. 文档

- 根 `README.md`：§4 增加"结果页刷新 / 查看上次结果 / 只显示本次注释"说明；
  §5 功能注释增加 CDS 预填说明；§7「找不到 minimap2」按新的解析顺序重写。
- `README-CN.md`：「运行状态」补结果页刷新与日志三行；功能注释补预填；外部工具补解析顺序。
- `02_code/PythonGUI/README.md`：界面功能（新按钮、清空规则、预填）、
  新增"安装目录与比对程序的定位顺序"一节、自测清单说明。
- `release/03_GUI/README.md`、`00_materials/tutorial.md`：按钮表、CDS 字段与预填、清空规则。

## 7. 仍未做 / 需要决定

1. **发布产物未重建**：本轮改了 `nanoamp_gui/app.py`、`r_runner.py`，而
   `release/03_GUI/nanoamp.exe` 与 setup 资产仍是旧代码；已上传的 v0.1.5 也因此不含本次修复。
   按"只提交"的指示我没有重建，需要时再说一声（重建会改变
   `release/_build/SHA256SUMS.txt` 里的 setup 校验值）。
2. `D:\tools\R` 仍为空：三个需要 R 的自测脚本无法复跑（脚本 `tmp/r_setup_and_verify.ps1` 可离线恢复）。
3. 上游回灌（Linux 仓库的 L1–L13）与既有未做项（C4 磁盘满、C9 ARM64、E2 高 DPI、
   GUI 大表虚拟化）。
