R_PKG := 02_code/r

.PHONY: help install test check cli gui gui-python gui-exe gui-test release install-exe release-check release-test deps toolchain offline-bundle offline-install clean-builds

help:
	@echo "nanoamp (Windows variant) project targets:"
	@echo "  make install          Install the R package (R CMD INSTALL $(R_PKG))"
	@echo "  make test             Run testthat tests"
	@echo "  make check            Build and R CMD check into 04_builds/r"
	@echo "  make cli              Run 'nanoamp doctor' from the repository CLI"
	@echo "  make gui              Launch the Shiny GUI (browser based)"
	@echo "  make gui-python       Launch the Python/Tkinter desktop GUI"
	@echo "  make gui-exe          Rebuild 02_code/PythonGUI/dist/nanoamp.exe"
	@echo "  make gui-test         Run the Python GUI self-tests"
	@echo "  make release          Rebuild the whole release/ tree payload"
	@echo "  make install-exe      Rebuild release/install.exe and uninstall.exe"
	@echo "  make release-test     Verify the release layout and installer logic"
	@echo "  make deps             Show how the bundled minimap2.exe was built"
	@echo "  make toolchain        Install the MSYS2/MINGW-w64 build toolchain"
	@echo "  make offline-bundle   Fetch the offline installer bundle into 03_dependence/offline-bundle/"
	@echo "  make offline-install  Install everything from the bundle (no network)"
	@echo "  make clean-builds     Remove 04_builds/r contents"

install:
	R CMD INSTALL $(R_PKG)

test:
	Rscript -e 'devtools::test("$(R_PKG)", reporter = "summary")'

check:
	mkdir -p 04_builds/r
	R CMD build $(R_PKG) --no-build-vignettes
	mv nanoamp_*.tar.gz 04_builds/r/
	cd 04_builds/r && R CMD check --no-manual --no-build-vignettes nanoamp_*.tar.gz

cli:
	sh 02_code/cli/nanoamp doctor

gui:
	Rscript 02_code/gui/run_gui.R

# Python/Tkinter desktop window. Ships as 02_code/PythonGUI/dist/nanoamp.exe.
gui-python:
	python 02_code/PythonGUI/run_gui.py

gui-exe:
	python 02_code/PythonGUI/build_exe.py

gui-test:
	python 02_code/PythonGUI/tests/test_headless.py
	python 02_code/PythonGUI/tests/test_e2e.py
	python 02_code/PythonGUI/tests/test_frozen.py

# --- release/ : the bundle that is handed to a user -------------------------
# Rebuilds the payload pieces (R package tarball, GUI exe) into release/.
release:
	mkdir -p 04_builds/r release/01_R-package release/03_GUI
	R CMD build $(R_PKG) --no-build-vignettes
	mv nanoamp_*.tar.gz release/01_R-package/
	cp -f release/01_R-package/nanoamp_*.tar.gz 04_builds/r/ 2>/dev/null || true
	python 02_code/PythonGUI/build_exe.py
	cp -f 02_code/PythonGUI/dist/nanoamp.exe release/03_GUI/nanoamp.exe
	@echo "Now run: make install-exe"

install-exe:
	python release/_installer/build_exe.py

release-test:
	python release/_installer/test_installer_logic.py
	python release/_installer/test_release_layout.py
	python release/_installer/test_window_fit.py
	python release/_installer/test_locked_file_retry.py
	python release/_installer/test_install_path_validation.py
	python release/_installer/test_r_shortcut_cleanup.py
	python release/_installer/test_r_version_choice.py
	python release/_installer/test_pinned_deps.py

release-check:
	release/install.exe --check

release-uninstall:
	release/uninstall.exe

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
	rm -rf 04_builds/r/*
