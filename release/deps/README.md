# deps/ —— 固定版本的依赖清单

`pinned-R4.6.tsv` 记录 nanoamp 需要的**每一个 R 依赖包的确切版本**，以及它的
大小、md5、sha256 和依赖关系。它是从离线依赖包（`release/_offline/r-packages`）
生成的，**唯一的用途**是让安装器在没有 `_offline/` 目录时也能安装出**完全相同**的
一套依赖，而不是"从镜像上抓当前最新版"。

```text
# r_tag            4.6                       ← 依赖包编译所用的 R 小版本
# bioconductor     3.23                      ← Bioconductor 版本（包 URL 要用）
# r_installer      R-4.6.1-win.exe  91749976  c5424c40…   ← 需要的 R 版本 + 大小 + sha256
# packages         109
package  version  bytes  md5  sha256  deps
abind    1.4-8    67558  …    …       methods;utils
```

## 安装器如何使用本清单

1. `install.exe` 先检查旁边有没有 `_offline/`：
   - **有** → 用离线包安装，不访问网络（原有的行为）；
   - **没有** → 读本清单，进入联网模式。
2. 联网模式先**测速选源**：并发拉取每个镜像的 `bin/windows/contrib/4.6/PACKAGES.gz`
   （体积小、必然存在），按实测速度排序，选最快的；失败/超时的镜像排到最后备选。
3. 然后**按依赖顺序**（清单里的 `deps` 列做拓扑排序）逐个下载。
   CRAN 包走 `<镜像>/CRAN/bin/windows/contrib/4.6/`，
   Bioconductor 包走 `<镜像>/packages/3.23/bioc/bin/windows/contrib/4.6/`；
   某个镜像取不到就换下一个。
4. **验收标准是"版本"而不是"字节"**：下载后读 zip 里 `DESCRIPTION` 的
   `Package`/`Version`，必须与本清单完全一致；对不上就换镜像，全部失败则明确报错
   并建议改用离线包。原因是镜像会重新编译二进制：同一个版本、不同字节属常态
   （例如 `generics_0.1.4.zip` 官方今天 86,409 B，离线包里是 85,804 B）。
   sha256 仍然有用：校验一致会在日志里记为"与离线包逐字节相同"，
   不一致则记为"镜像重新编译的同版本文件"，两者都接受。
5. 机器上没有 R、也没有 `_offline/r/R-4.6.1-win.exe` 时，
   R 运行时也从同一镜像下载（大小与 sha256 与离线包里那个文件一致）。
6. 下载完成后一次性安装（`install.packages(files, repos = NULL, type = "win.binary")`），
   再校验关键包能否加载。

下载目录是临时目录，装完即删；需要避免重复下载时保留 `_offline/`（离线包）。

## 重新生成

```bash
# 先确保离线包是最新的（03_dependence/offline-bundle/fetch_offline_bundle.R）
python release/deps/build_pinned_manifest.py
```

脚本会读 `_offline/r-packages/bin/windows/contrib/4.6/PACKAGES` 与每个 `.zip`，
算出大小与摘要后写出本文件；如果清单里的版本与 zip 文件名不一致会直接报错退出。
修改后需要重建资产：`python release/_build/build_assets.py`。

## 镜像列表

写在 `release/_installer/install_nanoamp.py` 的 `MIRRORS` 里：清华 TUNA、
中科大 USTC、北外 BFSU、南大 NJU、阿里云、CRAN/Bioconductor 官方。
前四个同时镜像 CRAN 与 Bioconductor；官方作为最后备选。
