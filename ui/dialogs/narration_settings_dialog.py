"""
Pre-narration configuration dialog.

Lets the user choose voice, reading speed, page range,
and content filtering options before starting narration.
"""

from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QSlider,
    QSpinBox,
    QVBoxLayout,
)

from narration.tts.model_manager import KNOWN_VOICES


class NarrationSettingsDialog(QDialog):
    """
    Configuration dialog shown before narration starts.

    Maps settings to :class:`NarrationConfig` fields via
    the controller's ``update_config()`` method.
    """

    def __init__(self, controller, total_pages: int, start_page: int = 0, parent=None):
        super().__init__(parent)
        self._controller = controller
        self._total_pages = total_pages
        self._start_page = start_page
        self.setWindowTitle("Narration Settings")
        self.setMinimumWidth(400)
        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(12)

        # --- Voice section ---
        voice_group = QGroupBox("Voice")
        voice_inner = QVBoxLayout(voice_group)

        self.voice_combo = QComboBox()
        voice_names = list(KNOWN_VOICES.keys())
        self.voice_combo.addItems(voice_names)
        # Select current config voice if present
        current_voice = self._controller._config.voice_name
        if current_voice in voice_names:
            self.voice_combo.setCurrentIndex(voice_names.index(current_voice))
        voice_inner.addWidget(self.voice_combo)

        layout.addWidget(voice_group)

        # --- Speed section ---
        speed_group = QGroupBox("Reading Speed")
        speed_inner = QVBoxLayout(speed_group)

        speed_row = QHBoxLayout()
        self.speed_slider = QSlider(Qt.Horizontal)
        self.speed_slider.setMinimum(50)
        self.speed_slider.setMaximum(200)
        self.speed_slider.setValue(int(self._controller._config.speed_multiplier * 100))
        self.speed_slider.setTickInterval(25)
        self.speed_slider.setTickPosition(QSlider.TicksBelow)
        self.speed_label = QLabel(f"{self.speed_slider.value() / 100:.2f}×")
        self.speed_slider.valueChanged.connect(
            lambda v: self.speed_label.setText(f"{v / 100:.2f}×")
        )
        speed_row.addWidget(self.speed_slider)
        speed_row.addWidget(self.speed_label)
        speed_inner.addLayout(speed_row)

        note = QLabel("This controls synthesis speed (prosody). "
                       "Playback speed is adjustable in the player bar.")
        note.setWordWrap(True)
        note.setStyleSheet("color: #8899AA; font-size: 11px;")
        speed_inner.addWidget(note)

        layout.addWidget(speed_group)

        # --- Page range section ---
        page_group = QGroupBox("Page Range")
        page_layout = QVBoxLayout(page_group)

        self.all_pages_check = QCheckBox("All pages")
        self.all_pages_check.setChecked(self._start_page == 0)
        self.all_pages_check.toggled.connect(self._on_all_pages_toggled)
        page_layout.addWidget(self.all_pages_check)

        range_row = QHBoxLayout()
        self.start_spin = QSpinBox()
        self.start_spin.setMinimum(1)
        self.start_spin.setMaximum(self._total_pages)
        self.start_spin.setValue(self._start_page + 1)
        range_row.addWidget(QLabel("From:"))
        range_row.addWidget(self.start_spin)

        self.end_spin = QSpinBox()
        self.end_spin.setMinimum(1)
        self.end_spin.setMaximum(self._total_pages)
        self.end_spin.setValue(self._total_pages)
        range_row.addWidget(QLabel("To:"))
        range_row.addWidget(self.end_spin)

        page_layout.addLayout(range_row)

        if self._start_page > 0:
            hint = QLabel(f"Starting from page {self._start_page + 1}")
            hint.setStyleSheet("color: #4a9eff; font-size: 11px;")
            page_layout.addWidget(hint)

        self._on_all_pages_toggled(self.all_pages_check.isChecked())
        layout.addWidget(page_group)

        # --- Content filtering ---
        filter_group = QGroupBox("Content Filtering")
        filter_layout = QVBoxLayout(filter_group)

        self.skip_footnotes_check = QCheckBox("Skip footnotes")
        self.skip_footnotes_check.setChecked(self._controller._config.skip_footnotes)
        filter_layout.addWidget(self.skip_footnotes_check)

        self.skip_captions_check = QCheckBox("Skip captions")
        self.skip_captions_check.setChecked(self._controller._config.skip_captions)
        filter_layout.addWidget(self.skip_captions_check)

        self.strip_refs_check = QCheckBox("Strip citation markers [N]")
        self.strip_refs_check.setChecked(self._controller._config.strip_references)
        filter_layout.addWidget(self.strip_refs_check)

        self.announce_pages_check = QCheckBox("Announce page numbers")
        self.announce_pages_check.setChecked(self._controller._config.announce_pages)
        filter_layout.addWidget(self.announce_pages_check)

        layout.addWidget(filter_group)

        # --- Buttons ---
        buttons = QDialogButtonBox(
            QDialogButtonBox.Ok | QDialogButtonBox.Cancel
        )
        buttons.button(QDialogButtonBox.Ok).setText("Start Narration")
        buttons.accepted.connect(self._on_accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def _on_all_pages_toggled(self, checked: bool):
        self.start_spin.setEnabled(not checked)
        self.end_spin.setEnabled(not checked)
        if checked:
            self.start_spin.setValue(1)
            self.end_spin.setValue(self._total_pages)

    def _on_accept(self):
        """Apply settings to controller config and accept."""
        self._controller.update_config(
            voice_name=self.voice_combo.currentText(),
            speed_multiplier=self.speed_slider.value() / 100.0,
            skip_footnotes=self.skip_footnotes_check.isChecked(),
            skip_captions=self.skip_captions_check.isChecked(),
            strip_references=self.strip_refs_check.isChecked(),
            announce_pages=self.announce_pages_check.isChecked(),
        )

        if self.all_pages_check.isChecked():
            self._controller.update_config(page_range=None)
        else:
            start = self.start_spin.value() - 1  # 0-based
            end = self.end_spin.value() - 1
            self._controller.update_config(page_range=(start, end))
            # Update start_page for the caller
            self._start_page = start

        self.accept()

    @property
    def selected_start_page(self) -> int:
        return self._start_page
