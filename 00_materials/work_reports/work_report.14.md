# 工作报告 14：修掉「机器上已有 R 4.5 就装不上」的缺陷

> 日期：2026-09-24
> 关联：`work_report.13.md`
> 触发：用户在另一台 Win11 机器（自带 R 4.5）上运行 **v0.1.2** 的 `install.exe`，
> 安装器报告"找到 R 4.5"，随后拒绝继续 —— 既没用系统 R，也没装自带的 R 4.6

---

## 1. 问题复现与根因

用户现象：`install.exe` 找到 R 4.5 → 报「安装包内没有适配 R 4.5 的依赖包」→ 退出。

代码里是两步配合出来的：

```python
# release/_installer/install_nanoamp.py（旧）
def _ensure_r(self):
    existing = find_rscript()
    if existing and r_supported(existing):      # ← 只检查版本 ≥ 4.2
        self.rscript = existing                  # ← 于是就用了 R 4.5
        return True
    ...

def _install_r_dependencies(self):
    tag = f"{ver[0]}.{ver[1]}"                   # ← "4.5"
    pkg_dir = self.ctx.extra_dir(tag)
    if not pkg_dir.is_dir():                     # ← 包里只有 contrib/4.6
        self.say("安装包内没有适配 R 4.5 的依赖包。")
        self.say("安装包提供的是：4.6")
        self.say("请安装与安装包匹配的 R 版本，或获取对应版本的安装包。")
        return False                             # ← 安装失败
```

关键点：**R 的二进制包不跨小版本兼容**，所以 `_offline/r-packages/bin/windows/contrib/4.6`
里的 109 个包只能在 R 4.6 上用。旧逻辑只看"R 够不够新（≥ 4.2）"，于是选中 4.5，
依赖步骤必然失败；而包里明明带着 R 4.6 的安装器（`_offline/r/R-4.6.1-win.exe`），
**却从不回退去装它**。用户被卡在一个自己无法解决的提示上。

---

## 2. 修复：按"包能不能用"选 R，而不是按"够不够新"

新增一个纯函数（便于测试），把决策从"版本下限"改成"**系统 R 必须与包内依赖包同版本**"：

```python
def r_choice(available_tags, system_version, minimum=(MIN_R_MAJOR, MIN_R_MINOR)) -> str:
    if system_version is None:                       return "bundled"
    if system_version < minimum:                     return "bundled"
    if available_tags and f"{system_version[0]}.{system_version[1]}" not in available_tags:
        return "bundled"                             # ← 4.5 对 4.6 的包：改装自带的 R
    return "system"
```

`_ensure_r()` 改为用它，并把话说清楚：

```text
检测到已安装的 R 4.5，但安装包里的依赖包是为 R 4.6 编译的（R 的小版本之间二进制不兼容）。
将改为安装随包提供的 R：它只装在 nanoamp 自己的目录里，不会改动也不会卸载你现有的 R。
```

行为矩阵：

| 机器上的 R | 包内依赖包 | 结果 |
|---|---|---|
| 无 | 4.6 | 安装自带 R 4.6（原有行为） |
| 4.6.x | 4.6 | **直接使用**系统 R（不重复装 R） |
| 4.5 / 4.4 / 5.0（≠ 4.6） | 4.6 | **安装自带 R 4.6**，并说明原因（本次修复） |
| < 4.2 | 4.6 | 安装自带 R 4.6（原有行为） |
| 任意 | 包内没有任何依赖包 | 仍用系统 R（保持旧行为），失败时提示包不完整 |

依赖步骤那句"请安装与安装包匹配的 R 版本"也改成解释现状：正常情况下安装程序
会自动改用自带的 R，看到那一行说明包内缺 R 安装器或包不完整。

自带的 R 装在 `<安装目录>\R\R-runtime`，**不动、不卸载用户已有的 R**；
`config.ini` 里记下 `rscript=`，图形界面与 CLI 都从这里取（work_report.11 §9.1 已铺好）。

---

## 3. 新增测试

`release/_installer/test_r_version_choice.py`（已加入 `make release-test`）：

* **决策表 10 例**：4.6 对 4.6 → system；**4.5 对 4.6 → bundled（用户的场景）**；
  4.4 / 5.0 / 4.2 / 3.6 / 无 R → bundled；包内无依赖包 → 沿用旧规则；多标签包 → 取匹配的。
* **真实切换路径**（把 R 安装器与版本读取打桩，不产生任何副作用）：
  断言安装程序**没有失败**、`rscript` 落在 `<安装目录>\R\R-runtime`、
  日志里出现"为 R 4.6 编译的"、"R 4.5"、"不会改动也不会卸载你现有的 R"；
  以及反例：系统 R 正好是 4.6 时**仍然优先用它**，不会白装一份 R。

```text
PASS  R version choice: matching system R is used, mismatching R falls back to the bundled one
```

这台机器上没有 R 4.5 可供实测，因此用"决策表 + 打桩切换"覆盖该分支；
但**"从资产安装"的整条链路**（含系统 R 4.6 的检测与复用）在沙箱里真跑了一遍，见 §4。

---

## 4. 验证清单

| 项目 | 结果 |
|---|---|
| `test_r_version_choice.py`（新） | **PASS**（16 项检查） |
| 另外 6 个发布测试 | `test_installer_logic` OK、`test_install_path_validation` PASS（13+8）、`test_locked_file_retry` PASS 4/4、`test_r_shortcut_cleanup` PASS、`test_window_fit` PASS 6/6、`test_release_layout` ALL DELIVERABLE CHECKS PASSED |
| `install.exe` / `uninstall.exe` | 重新打包（含本次修复） |
| 两个发布资产 | 重新打包并逐条 sha256 自校验：`nanoamp-0.1.3-windows-setup.zip`（14 个条目）、`nanoamp-0.1.0-windows-offline-deps.zip`（113 个条目）；`SHA256SUMS.txt` 已更新 |
| 从新资产静默安装（沙箱） | **安装成功**：`检测到已安装的 R 4.6：D:\tools\R\R-4.6.1\bin\Rscript.exe` → 109 包 → 主程序 → 启动器/minimap2/GUI → 自检通过 |
| 安装后实跑 | `nanoamp call`（E4-3, mode A）：`n_reads_total` 438、`mapping_rate` 0.997717、`exact_reference_proportion` 0.314554，与文档一致 |

---

## 5. 给手上还是 0.1.2 的用户的临时办法

1. 先从包里运行 `_offline\r\R-4.6.1-win.exe`（或在 R 官网装 R 4.6.x，
   `%ProgramFiles%\R\R-4.6.1` / `D:\tools\R\R-4.6.1` 都在安装器的搜索路径里），
   再重新运行 `install.exe` —— 它检测到 4.6 就会直接用；
2. 或等 0.1.3 的安装包（本修复已进仓库与资产）。

---

## 6. 遗留

1. **远端 Release 仍是 v0.1.2**（2026-09-20 发布）：它既没有本轮的 R 版本修复，
   也没有 work_report.12 的 `align.R` 空格路径修复。仓库里 0.1.3 的两个资产已就绪
   （`release/SHA256SUMS.txt`），**尚未上传**，等待确认后再发。
2. 干净机器上"没有系统 R → 装自带 R"这一分支仍未在真机实测（本机有 R 4.6，
   走的是"检测到已安装的 R"）；不过包内 R 安装器的调用参数、安装目录、
   快捷方式抑制逻辑与本次沙箱安装共用同一条路径。
3. `install.spec` / `uninstall.spec` 的 `onefile=False` 与实际 onefile 产物不一致，
   继续记录未改（work_report.12 §8）。
