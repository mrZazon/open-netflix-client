.PHONY: run install dev clean lint typecheck test build-appimage build-flatpak \
        build-deb build-rpm install-desktop-entry uninstall-desktop-entry

VENV = .venv
PYTHON = python3

run:
	$(PYTHON) netflix-client.py

install:
	$(PYTHON) -m pip install -e .

dev:
	$(PYTHON) -m pip install -e ".[dev]"

clean:
	rm -rf build/ dist/ *.spec __pycache__/
	find . -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
	find . -name "*.pyc" -delete

lint:
	ruff check app/

typecheck:
	mypy app/ --ignore-missing-imports

test:
	python -m pytest tests/ -v

build-pyinstaller:
	pyinstaller --clean --onefile --name "netflix-client" \
		--add-data "app/css/style.qss:app/css/" \
		--add-data "app/assets/icon.svg:app/assets/" \
		--hidden-import "PySide6.QtWebEngine" \
		--hidden-import "PySide6.QtWebEngineWidgets" \
		--hidden-import "keyring" \
		netflix-client.py

install-desktop-entry:
	mkdir -p ~/.local/share/applications
	mkdir -p ~/.local/share/icons/hicolor/scalable/apps
	mkdir -p ~/.local/share/icons/hicolor/48x48/apps
	cp packaging/netflix-client.desktop ~/.local/share/applications/
	cp app/assets/icon.svg ~/.local/share/icons/hicolor/scalable/apps/netflix-client.svg
	update-desktop-database ~/.local/share/applications/ 2>/dev/null || true

uninstall-desktop-entry:
	rm -f ~/.local/share/applications/netflix-client.desktop
	rm -f ~/.local/share/icons/hicolor/scalable/apps/netflix-client.svg
	update-desktop-database ~/.local/share/applications/ 2>/dev/null || true

build-appimage:
	$(MAKE) build-pyinstaller
	# Use appimagetool to convert to AppImage
	# See: https://github.com/AppImage/AppImageKit

build-flatpak:
	flatpak-builder build-dir packaging/netflix-client.flatpak.yml --force-clean
	flatpak build-export repo build-dir
	flatpak build-bundle repo netflix-client.flatpak

build-deb:
	# Requires dpkg-deb
	mkdir -p build/deb/usr/bin
	mkdir -p build/deb/usr/share/applications
	mkdir -p build/deb/usr/share/icons/hicolor/scalable/apps
	cp packaging/debian/control build/deb/DEBIAN/
	cp packaging/netflix-client.desktop build/deb/usr/share/applications/
	cp app/assets/icon.svg build/deb/usr/share/icons/hicolor/scalable/apps/netflix-client.svg
	cp netflix-client.py build/deb/usr/bin/netflix-client
	dpkg-deb --build build/deb build/netflix-client.deb

build-rpm:
	# Requires rpmbuild
	mkdir -p build/rpm/SOURCES
	cp packaging/netflix-client.spec build/rpm/
	# Build with: rpmbuild -ba build/rpm/netflix-client.spec
