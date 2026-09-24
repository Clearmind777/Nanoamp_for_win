# `release/_build/` —— 打包工作区

这个文件夹只跟"把 `release/` 打成一个能上传的 zip"有关，**用户不需要它**。
`release/` 根目录只留使用者解压后要看到的东西（`install.exe`、`01_R-package/`、
`02_CLI/`、`03_GUI/`、`deps/`、`_offline/`、`README.md`）和安装器源码
（`release/_installer/`）。

```text
release/_build/
|-- build_assets.py                   打包脚本（内容逐条 sha256 自校验）
|-- SHA256SUMS.txt                    产物的 sha256 —— 这个进 Git，便于对账
|-- nanoamp-0.1.5-windows-setup.zip        ~34 MB  ← 上传这个
`-- nanoamp-0.1.0-windows-offline-deps.zip  ~248 MB ← 可选（离线依赖）
```

## 用法

```powershell
# 打包（重写两个 zip 与 SHA256SUMS.txt）
python release\_build\build_assets.py

# 只校验：解压每条内容与 release\ 下的源材料逐字节比对
python release\_build\build_assets.py --verify-only

# 与已发布的资产对账（先下载：gh release download v0.1.5 -D tmp\published）
python release\_build\build_assets.py --compare-published tmp\published\setup.zip tmp\published\offline-deps.zip
```

zip 里的根目录固定是 `nanoamp-windows/`，源材料取自上一级目录（`release/`）。
用固定时间戳写入，所以**同样的源材料给出同样的字节**：本文档旁边那两个
sha256 与重新打包的结果一致。

## 为什么不进 Git

- 两个 zip 合计约 **282 MB**，其中离线依赖包 248 MB，**超过 GitHub 单文件
  100 MiB 的硬限制**；
- 它们是构建产物，随时可由源材料重新生成。

所以 `.gitignore` 排除 `release/_build/*.zip`，只提交 `SHA256SUMS.txt`。
重新生成的 zip 若 sha256 与清单一致，就说明源材料没有被改动过。
