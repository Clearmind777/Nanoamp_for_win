R_PKG := 02_code/r

.PHONY: help install test check cli gui gui-python gui-exe gui-test release install-exe release-check release-test deps toolchain offline-bundle offline-install clean-builds

help:
	@echo "nanoamp (Windows variant) project targets:"
	@echo "  make install          Install the R package (R CMD INSTALL $(R_PKG))"
	@echo "  make test             Run testthat tests"
	@echo "  make check            Build and R CMD check into 05_builds/r"
	@echo "  make cli              Run 'nanoamp doctor' from the repository CLI"
	@echo "  make gui              Launch the Shiny GUI (browser based)"
	@echo "  make gui-python       Launch the Python/Tkinter desktop GUI"
	@echo "  make gui-exe          Rebuild 06_GUI/dist/nanoamp.exe"
	@echo "  make gui-test         Run the Python GUI self-tests"
	@echo "  make release          Rebuild the whole release/ tree payload"
	@echo "  make install-exe      Rebuild release/install.exe"
	@echo "  make release-test     Verify the release layout and installer logic"
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

# Python/Tkinter desktop window. Ships as 06_GUI/dist/nanoamp.exe.
gui-python:
	python 06_GUI/run_gui.py

gui-exe:
	python 06_GUI/build_exe.py

gui-test:
	python 06_GUI/tests/test_headless.py
	python 06_GUI/tests/test_e2e.py
	python 06_GUI/tests/test_frozen.py

# --- release/ : the bundle that is handed to a user -------------------------
# Rebuilds the payload pieces (R package tarball, GUI exe) into release/.
release:
	mkdir -p 05_builds/r release/01_R-package release/03_GUI
	R CMD build $(R_PKG) --no-build-vignettes
	mv nanoamp_*.tar.gz release/01_R-package/
	cp -f release/01_R-package/nanoamp_*.tar.gz 05_builds/r/ 2>/dev/null || true
	python 06_GUI/build_exe.py
	cp -f 06_GUI/dist/nanoamp.exe release/03_GUI/nanoamp.exe
	@echo "Now run: python release/_installer/build_installer_exe.py"

install-exe:
	python release/_installer/build_installer_exe.py

release-test:
	python release/_installer/test_installer_logic.py
	python release/_installer/test_release_layout.py

release-check:
	release/install.exe --check

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
