# 工作报告 16：整理 `release/` 目录

- 日期：2026-09-24
- 仓库：`Nanoamp_for_win`（Windows 专用）
- 上一轮：`work_report.15.md`（不装离线包也能装完 + 补上 minimap2）
- 本轮委托（用户原话）：「release\ 文件夹下太乱了，请你整理一下」

---

## 1. 问题：交付负载和开发脚手架混在一起

`release/` 是**要交给使用者的目录**（解压后双击 `install.exe`），但它同时又是开发
工作区，于是根目录里混着四类东西：

| 类别 | 内容 | 是否该留在根目录 |
|---|---|---|
| 使用者要看到的负载 | `install.exe`、`uninstall.exe`、`README.md`、`01_R-package/`、`02_CLI/`、`03_GUI/`、`deps/`、`_offline/` | **必须**（zip 的条目路径就是它们） |
| 只跟打包有关 | `build_assets.py`、`SHA256SUMS.txt`、两个 `.zip` | 不该 |
| 只跟排查有关 | `diagnose_install_env.py` / `.bat`（与 `_installer/` 里**逐字节重复**） | 不该 |
| 生成物 | `__pycache__/`、`_installer/build/`（PyInstaller 中间目录）、`nanoamp_install.log`、下载的旧 `nanoamp-0.1.3-windows-setup.zip` | 不该 |

> 注意：根目录**不能**随便挪的是第一类。`build_assets.py` 的 `SETUP_ITEMS` 是相对
> `release/` 的路径，zip 里的 `nanoamp-windows/` 就是它们的镜像。所以整理的方向是
> "把其余三类收起来"，不是"重排负载"。

## 2. 做法

### 2.1 删掉生成物（46.6 MB）

```text
release/__pycache__/
release/_installer/__pycache__/
release/_installer/build/          PyInstaller 中间目录（15 MB）
release/nanoamp_install.log
release/nanoamp-0.1.3-windows-setup.zip   下载来对账的已发布资产，可随时重新下载
```

这些都已被 `.gitignore` 覆盖，删掉不影响任何提交内容。新增 `make clean-scratch`
把它们一次清掉。

### 2.2 新增 `release/_build/`：打包工作区

```text
release/_build/
|-- build_assets.py        从 release/ 打包（原 release/build_assets.py）
|-- SHA256SUMS.txt         产物摘要（原 release/SHA256SUMS.txt，仍进 Git）
|-- README.md              说明这个目录是什么、怎么用（新增）
|-- nanoamp-0.1.5-windows-setup.zip          构建产物，不进 Git
`-- nanoamp-0.1.0-windows-offline-deps.zip   构建产物，不进 Git
```

`build_assets.py` 现在显式区分两个路径，语义比原来的单个 `HERE` 清楚：

```python
OUT  = Path(__file__).resolve().parent   # 写 zip 与 SHA256SUMS.txt（release/_build/）
TREE = OUT.parent                        # 打包源材料（release/）
```

### 2.3 去重

`diagnose_install_env.py` / `.bat` 在 `release/` 根与 `release/_installer/` 里
**完全相同**（sha256 一致）。保留 `_installer/` 里的那份（安装器源码的家），
删掉根目录副本；`release/README.md` 明确写出它的位置。

### 2.4 整理后的根目录

```text
release/
|-- install.exe  uninstall.exe  README.md    ← 使用者要看到的
|-- 01_R-package/  02_CLI/  03_GUI/  deps/  _offline/
|-- _installer/    安装器/卸载器源码与自测（含 diagnose_install_env.*）
`-- _build/        打包工作区（zip、SHA256SUMS.txt、build_assets.py）
```

从 16 个顶层条目变成 12 个，且一眼能分出"给人用的"和"开发用的"。

## 3. 连带改动

| 文件 | 改动 |
|---|---|
| `release/_build/build_assets.py` | `HERE` → `OUT` / `TREE`；输出写到 `_build/`；docstring 与用法更新 |
| `release/_build/README.md` | 新增：这个目录是什么、怎么打包/校验/对账、为什么不进 Git |
| `release/README.md` | 目录结构表重写；所有 `release/build_assets.py` → `release/_build/build_assets.py`；`diagnose_install_env` 位置 |
| `README.md`（根） | 无需改（没有引用打包脚本） |
| `.gitignore` | `release/nanoamp-*-windows-{setup,offline-deps}.zip` → `release/_build/*.zip` |
| `release/.gitignore` | 补充说明 `_build/` 里哪些文件进 Git |
| `Makefile` | 新增 `release-assets`（打包）与 `clean-scratch`（清生成物）目标 |
| `release/_installer/test_release_layout.py` | setup 资产改到 `release/_build/` 下查找 |
| `release/_installer/test_pinned_deps.py` | 从 `_build/` 导入 `build_assets`，并断言 `TREE`/`OUT` 指向正确 |
| `release/_installer/build_exe.py` | 提示文案里的路径 |
| `release/deps/README.md` | 重建资产命令的新路径；顺手修掉了写错的 `tmp/make_pinned_manifest.py` |
| `release/deps/build_pinned_manifest.py` | docstring 里的命令路径 |

`00_materials/work_reports/work_report.15.md` 等历史报告保持原样（它们记录的是
当时的状态）；其中出现的 `python release\build_assets.py` 现已写作
`python release\_build\build_assets.py`。

## 4. 验证

1. **从新位置重新打包，产物逐字节不变**（除文档条目外）：

   ```text
   built _build/nanoamp-0.1.5-windows-setup.zip: 18 files, 35.9 MB uncompressed, 34.4 MB packed
   built _build/nanoamp-0.1.0-windows-offline-deps.zip: 113 files, 252.5 MB uncompressed, 248.0 MB packed
      verified nanoamp-0.1.5-windows-setup.zip: 18 entries match the tree
      verified nanoamp-0.1.0-windows-offline-deps.zip: 113 entries match the tree
   ```

   离线依赖包的 sha256 与整理前**完全一致**（`2db72289…`），说明搬运没有碰到任何负载；
   setup 包因为内部含 `release/README.md`（本轮改过）而哈希变化，属预期。

2. `--verify-only` 通过：两条 zip 的每个条目与 `release/` 下源材料逐字节相同。
3. 受影响的测试通过：`test_release_layout.py`（含 "setup 资产里含 bin/minimap2.exe 与
   deps 清单"）、`test_pinned_deps.py`（含 `TREE`/`OUT` 断言）。
4. 用**整理后重新打包**的 setup 资产重跑联网安装 + 安装后 CLI/GUI 验证（见 §5）。
5. `git status` 与预期一致：根目录 `build_assets.py`、`SHA256SUMS.txt`、
   `diagnose_install_env.*` 删除，`_build/{build_assets.py,SHA256SUMS.txt,README.md}`
   新增，两个 zip 仍被忽略。

## 5. 复现

```powershell
# 打包（产物在 release/_build/）
python release\_build\build_assets.py
make release-assets

# 只校验
python release\_build\build_assets.py --verify-only

# 清掉生成物
make clean-scratch
```

## 6. 遗留

1. 两个 zip 仍然合计约 282 MB、仍然不进 Git：离线依赖包超过 GitHub 单文件 100 MiB
   的硬限制。`release/_build/SHA256SUMS.txt` 是唯一的对账凭据。
2. v0.1.4 / v0.1.5 仍未发布（沿用上一轮的决定）。
3. 如果以后还想更彻底（把 240 MB 的 `_offline/` 源材料也挪出去），要动
   `install.exe` 的负载发现逻辑与测试，本轮没做。
