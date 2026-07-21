from __future__ import annotations

from pathlib import Path
from typing import Any, Dict

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QTabWidget, QWidget,
    QLabel, QCheckBox, QComboBox, QLineEdit, QPushButton,
    QSlider, QSpinBox, QGroupBox, QFormLayout, QFileDialog,
    QMessageBox, QDialogButtonBox,
)

from app.settings import settings


class SettingsDialog(QDialog):
    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Settings")
        self.setMinimumSize(600, 450)
        self.resize(640, 500)
        self._setup_ui()
        self._load_settings()

    def _setup_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setSpacing(8)

        tabs = QTabWidget(self)

        tabs.addTab(self._general_tab(), "General")
        tabs.addTab(self._appearance_tab(), "Appearance")
        tabs.addTab(self._downloads_tab(), "Downloads")
        tabs.addTab(self._profiles_tab(), "Profiles")
        tabs.addTab(self._performance_tab(), "Performance")
        tabs.addTab(self._privacy_tab(), "Privacy")
        tabs.addTab(self._shortcuts_tab(), "Shortcuts")

        layout.addWidget(tabs)

        buttons = QDialogButtonBox(self)
        buttons.addButton("Reset", QDialogButtonBox.ButtonRole.ResetRole)
        buttons.addButton("Export", QDialogButtonBox.ButtonRole.ActionRole)
        buttons.addButton("Import", QDialogButtonBox.ButtonRole.ActionRole)
        buttons.addButton(QDialogButtonBox.StandardButton.Ok)
        buttons.addButton(QDialogButtonBox.StandardButton.Cancel)

        buttons.button(QDialogButtonBox.StandardButton.Ok).clicked.connect(self._save_and_close)
        buttons.button(QDialogButtonBox.StandardButton.Cancel).clicked.connect(self.reject)
        buttons.button(QDialogButtonBox.ButtonRole.ResetRole).clicked.connect(self._reset_settings)
        buttons.button(QDialogButtonBox.ButtonRole.ActionRole)  # Export
        export_btn = buttons.button(QDialogButtonBox.ButtonRole.ActionRole)  # Export
        import_btn = buttons.buttons()[-2]  # Import

        layout.addWidget(buttons)

    def _general_tab(self) -> QWidget:
        tab = QWidget()
        form = QFormLayout(tab)
        form.setSpacing(12)
        form.setContentsMargins(16, 16, 16, 16)

        self._launch_minimized = QCheckBox("Launch minimized to tray")
        form.addRow("", self._launch_minimized)

        self._auto_reconnect = QCheckBox("Auto-reconnect on connection loss")
        form.addRow("", self._auto_reconnect)

        self._single_instance = QCheckBox("Allow only one instance")
        form.addRow("", self._single_instance)

        return tab

    def _appearance_tab(self) -> QWidget:
        tab = QWidget()
        form = QFormLayout(tab)
        form.setSpacing(12)
        form.setContentsMargins(16, 16, 16, 16)

        self._dark_mode = QComboBox()
        self._dark_mode.addItems(["System", "Dark", "Light"])
        form.addRow("Theme:", self._dark_mode)

        self._rounded_corners = QCheckBox("Use rounded corners")
        form.addRow("", self._rounded_corners)

        self._compact_mode = QCheckBox("Compact mode")
        form.addRow("", self._compact_mode)

        self._show_tray = QCheckBox("Show system tray icon")
        form.addRow("", self._show_tray)

        return tab

    def _downloads_tab(self) -> QWidget:
        tab = QWidget()
        form = QFormLayout(tab)
        form.setSpacing(12)
        form.setContentsMargins(16, 16, 16, 16)

        dir_layout = QHBoxLayout()
        self._download_dir = QLineEdit()
        dir_layout.addWidget(self._download_dir)
        browse_btn = QPushButton("Browse...")
        browse_btn.clicked.connect(self._browse_download_dir)
        dir_layout.addWidget(browse_btn)
        form.addRow("Downloads directory:", dir_layout)

        self._max_parallel = QSpinBox()
        self._max_parallel.setRange(1, 10)
        form.addRow("Max parallel downloads:", self._max_parallel)

        self._bandwidth_limit = QSpinBox()
        self._bandwidth_limit.setRange(0, 100000)
        self._bandwidth_limit.setSuffix(" KB/s")
        self._bandwidth_limit.setSpecialValueText("Unlimited")
        form.addRow("Bandwidth limit:", self._bandwidth_limit)

        self._notify_complete = QCheckBox("Notify when download completes")
        form.addRow("", self._notify_complete)

        return tab

    def _profiles_tab(self) -> QWidget:
        tab = QWidget()
        layout = QVBoxLayout(tab)
        layout.setContentsMargins(16, 16, 16, 16)

        current = settings.get("profiles", "current", "Default")
        label = QLabel(f"Current profile: {current}")
        label.setStyleSheet("font-weight: 600; font-size: 14px;")
        layout.addWidget(label)

        help_text = QLabel(
            "Switch profiles from the Profiles menu in the menu bar.\n"
            "Each profile maintains its own cookies and cache."
        )
        help_text.setStyleSheet("color: #999; margin-top: 8px;")
        layout.addWidget(help_text)
        layout.addStretch()

        return tab

    def _performance_tab(self) -> QWidget:
        tab = QWidget()
        form = QFormLayout(tab)
        form.setSpacing(12)
        form.setContentsMargins(16, 16, 16, 16)

        self._hw_accel = QCheckBox("Hardware acceleration")
        form.addRow("", self._hw_accel)

        self._memory_cache = QSpinBox()
        self._memory_cache.setRange(64, 1024)
        self._memory_cache.setSuffix(" MB")
        form.addRow("Memory cache size:", self._memory_cache)

        self._disk_cache = QSpinBox()
        self._disk_cache.setRange(128, 4096)
        self._disk_cache.setSuffix(" MB")
        form.addRow("Disk cache size:", self._disk_cache)

        self._lazy_loading = QCheckBox("Lazy load tabs and views")
        form.addRow("", self._lazy_loading)

        clear_btn = QPushButton("Clear Cache")
        clear_btn.clicked.connect(self._clear_cache)
        form.addRow("", clear_btn)

        import os
        from app.utils.widevine import CDM_FILENAME
        cdm_dir = os.environ.get("QTWEBENGINE_CHROMIUM_FLAGS", "")
        cdm_found = False
        if "--widevine-path=" in cdm_dir:
            cdm_path = cdm_dir.split("--widevine-path=")[1].split()[0]
            cdm_found = os.path.isfile(cdm_path)
        if cdm_found:
            status = QLabel(f"DRM: OK ({cdm_path})")
            status.setStyleSheet("color: #2e7d32; font-weight: 600;")
        else:
            status = QLabel("DRM: Widevine CDM not found")
            status.setStyleSheet("color: #c62828; font-weight: 600;")
        form.addRow("DRM Status:", status)

        return tab

    def _privacy_tab(self) -> QWidget:
        tab = QWidget()
        form = QFormLayout(tab)
        form.setSpacing(12)
        form.setContentsMargins(16, 16, 16, 16)

        self._use_keyring = QCheckBox("Use OS keyring for credentials")
        form.addRow("", self._use_keyring)

        self._clear_cache_exit = QCheckBox("Clear cache on exit")
        form.addRow("", self._clear_cache_exit)

        self._save_cookies = QCheckBox("Save cookies between sessions")
        form.addRow("", self._save_cookies)

        return tab

    def _shortcuts_tab(self) -> QWidget:
        tab = QWidget()
        form = QFormLayout(tab)
        form.setSpacing(12)
        form.setContentsMargins(16, 16, 16, 16)

        self._shortcut_fields: Dict[str, QLineEdit] = {}
        shortcuts = [
            ("open_netflix", "Open Netflix"),
            ("play_pause", "Play / Pause"),
            ("mute", "Mute"),
            ("fullscreen", "Fullscreen"),
            ("picture_in_picture", "Picture in Picture"),
            ("always_on_top", "Always on Top"),
            ("reload", "Reload"),
            ("dev_tools", "Developer Tools"),
        ]
        for key, label_text in shortcuts:
            field = QLineEdit()
            field.setPlaceholderText("Press a key combination")
            self._shortcut_fields[key] = field
            form.addRow(f"{label_text}:", field)

        return tab

    def _load_settings(self) -> None:
        self._launch_minimized.setChecked(
            settings.get("general", "launch_minimized", False)
        )
        self._auto_reconnect.setChecked(
            settings.get("general", "auto_reconnect", True)
        )
        self._single_instance.setChecked(
            settings.get("general", "single_instance", True)
        )

        dark_mode = settings.get("appearance", "dark_mode", "system")
        idx = ["system", "dark", "light"].index(dark_mode) if dark_mode in ("system", "dark", "light") else 0
        self._dark_mode.setCurrentIndex(idx)
        self._rounded_corners.setChecked(
            settings.get("appearance", "rounded_corners", True)
        )
        self._compact_mode.setChecked(
            settings.get("appearance", "compact_mode", False)
        )
        self._show_tray.setChecked(
            settings.get("appearance", "show_tray_icon", True)
        )

        dl_dir = settings.get("downloads", "directory", "")
        self._download_dir.setText(dl_dir)
        self._max_parallel.setValue(
            settings.get("downloads", "max_parallel", 3)
        )
        self._bandwidth_limit.setValue(
            settings.get("downloads", "bandwidth_limit", 0)
        )
        self._notify_complete.setChecked(
            settings.get("downloads", "notify_completion", True)
        )

        self._hw_accel.setChecked(
            settings.get("performance", "hardware_acceleration", True)
        )
        self._memory_cache.setValue(
            settings.get("performance", "memory_cache_size", 256)
        )
        self._disk_cache.setValue(
            settings.get("performance", "disk_cache_size", 512)
        )
        self._lazy_loading.setChecked(
            settings.get("performance", "lazy_loading", True)
        )

        self._use_keyring.setChecked(
            settings.get("privacy", "use_keyring", True)
        )
        self._clear_cache_exit.setChecked(
            settings.get("privacy", "clear_cache_on_exit", False)
        )
        self._save_cookies.setChecked(
            settings.get("privacy", "save_cookies", True)
        )

        for key, field in self._shortcut_fields.items():
            field.setText(settings.get("shortcuts", key, ""))

    def _save_settings(self) -> None:
        settings.set("general", "launch_minimized",
                      self._launch_minimized.isChecked())
        settings.set("general", "auto_reconnect",
                      self._auto_reconnect.isChecked())
        settings.set("general", "single_instance",
                      self._single_instance.isChecked())

        dark_modes = ["system", "dark", "light"]
        settings.set("appearance", "dark_mode",
                      dark_modes[self._dark_mode.currentIndex()])
        settings.set("appearance", "rounded_corners",
                      self._rounded_corners.isChecked())
        settings.set("appearance", "compact_mode",
                      self._compact_mode.isChecked())
        settings.set("appearance", "show_tray_icon",
                      self._show_tray.isChecked())

        settings.set("downloads", "directory",
                      self._download_dir.text())
        settings.set("downloads", "max_parallel",
                      self._max_parallel.value())
        settings.set("downloads", "bandwidth_limit",
                      self._bandwidth_limit.value())
        settings.set("downloads", "notify_completion",
                      self._notify_complete.isChecked())

        settings.set("performance", "hardware_acceleration",
                      self._hw_accel.isChecked())
        settings.set("performance", "memory_cache_size",
                      self._memory_cache.value())
        settings.set("performance", "disk_cache_size",
                      self._disk_cache.value())
        settings.set("performance", "lazy_loading",
                      self._lazy_loading.isChecked())

        settings.set("privacy", "use_keyring",
                      self._use_keyring.isChecked())
        settings.set("privacy", "clear_cache_on_exit",
                      self._clear_cache_exit.isChecked())
        settings.set("privacy", "save_cookies",
                      self._save_cookies.isChecked())

        for key, field in self._shortcut_fields.items():
            settings.set("shortcuts", key, field.text())

    def _save_and_close(self) -> None:
        self._save_settings()
        self.accept()

    def _reset_settings(self) -> None:
        result = QMessageBox.question(
            self, "Reset Settings",
            "Are you sure you want to reset all settings to defaults?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if result == QMessageBox.StandardButton.Yes:
            settings.reset()
            self._load_settings()

    def _browse_download_dir(self) -> None:
        dir_path = QFileDialog.getExistingDirectory(
            self, "Select Downloads Directory"
        )
        if dir_path:
            self._download_dir.setText(dir_path)

    def _clear_cache(self) -> None:
        result = QMessageBox.question(
            self, "Clear Cache",
            "Clear browser cache and cookies?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if result == QMessageBox.StandardButton.Yes:
            from app.utils.config import CACHE_DIR
            import shutil
            try:
                shutil.rmtree(CACHE_DIR)
                CACHE_DIR.mkdir(parents=True, exist_ok=True)
                QMessageBox.information(self, "Cache Cleared",
                                        "Cache has been cleared.")
            except OSError as exc:
                QMessageBox.warning(self, "Error",
                                    f"Could not clear cache: {exc}")
