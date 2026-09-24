# windows-arm64

There are no native Windows ARM64 binaries for minimap2 or samtools.

Options, in order of preference:

1. use `aligner = "r"` (R-native alignment backend) — the only fully native
   option. It requires no external tool and works on any Windows architecture;
2. build minimap2 from source in an aarch64 MINGW-w64 environment
   (`mingw-w64-clang-aarch64-toolchain` in MSYS2). This is untested here; the
   x86_64 recipe in `../windows-x86_64/` is the verified one;
3. run the x86_64 Windows build under Windows-on-ARM emulation — copy
   `../windows-x86_64/bin/minimap2.exe` here and nanoamp resolves it as
   `windows-arm64/bin/minimap2.exe`.

samtools is not needed on any platform: `Rsamtools::asBam()` is the default
SAM -> BAM path.
