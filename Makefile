R_PKG := 02_code/r

.PHONY: help install test check cli gui deps toolchain offline-bundle offline-install clean-builds

help:
	@echo "nanoamp (Windows variant) project targets:"
	@echo "  make install          Install the R package (R CMD INSTALL $(R_PKG))"
	@echo "  make test             Run testthat tests"
	@echo "  make check            Build and R CMD check into 05_builds/r"
	@echo "  make cli              Run 'nanoamp doctor' from the repository CLI"
	@echo "  make gui              Launch the Shiny GUI"
	@echo "  make deps             Show how the bundled minimap2.exe was built"
	@echo "  make toolchain        Install the MSYS2/MINGW-w64 build toolchain"
	@echo "  make offline-bundle   Fetch the offline installer bundle into dist/"
	@echo "  make offline-install  Install everything from the bundle (no network)"
	@echo "  make clean-builds     Remove 05_builds/r contents"

install:
	R CMD INSTALL $(R_PKG)

test:
	Rscript -e 'devtools::test("$(R_PKG)", reporter = "summary")'

check:
	mkdir -p 05_builds/r
	R CMD build $(R_PKG) --no-build-vignettes
	mv nanoamp_*.tar.gz 05_builds/r/
	cd 05_builds/r && R CMD check --no-manual --no-build-vignettes nanoamp_*.tar.gz

cli:
	sh 02_code/cli/nanoamp doctor

gui:
	Rscript 02_code/gui/run_gui.R

# The Windows binary is already bundled; this only tells you how to rebuild it.
deps:
	@echo "minimap2 is already bundled at 03_dependence/windows-x86_64/bin/minimap2.exe"
	@echo "To rebuild it from source:"
	@echo "  make toolchain"
	@echo "  bash 03_dependence/windows-x86_64/build_minimap2.sh"

toolchain:
	pwsh -File 03_dependence/windows-x86_64/install_msys2_toolchain.ps1

offline-bundle:
	Rscript 03_dependence/offline-bundle/fetch_offline_bundle.R

offline-install:
	pwsh -File 03_dependence/offline-bundle/install_offline.ps1

clean-builds:
	rm -rf 05_builds/r/*
