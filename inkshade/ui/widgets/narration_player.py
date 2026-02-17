"""
Narration playback control bar — floating bottom bar with
play/pause, stop, page info, seek, speed, and progress.
"""

from PyQt5.QtCore import Qt, pyqtSignal, QSize
from PyQt5.QtGui import QColor, QIcon, QPixmap
from PyQt5.QtWidgets import (
    QComboBox,
    QFrame,
    QGraphicsDropShadowEffect,
    QHBoxLayout,
    QLabel,
    QSizePolicy,
    QSlider,
    QToolButton,
    QVBoxLayout,
    QWidget,
)


class NarrationPlayerBar(QFrame):
    """
    Persistent bottom bar shown during narration playback.

    Provides play/pause, stop, page indicator, seek slider,
    time display, speed control, and buffering indicator.
    """

    # Signals for parent wiring
    stop_requested = pyqtSignal()
    export_requested = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("NarrationPlayerBar")
        self._controller = None
        self._auto_scroll = True
        self._current_page_duration_ms: float = 0
        self._setup_ui()
        self.hide()

    # ------------------------------------------------------------------
    # UI setup
    # ------------------------------------------------------------------

    def _setup_ui(self):
        self.setFixedHeight(56)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)

        # Drop shadow
        shadow = QGraphicsDropShadowEffect(self)
        shadow.setBlurRadius(12)
        shadow.setOffset(0, -2)
        shadow.setColor(QColor(0, 0, 0, 80))
        self.setGraphicsEffect(shadow)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(12, 6, 12, 6)
        layout.setSpacing(10)

        # Play / Pause button
        self.play_pause_btn = QToolButton(self)
        self.play_pause_btn.setText("\u25B6")  # ▶
        self.play_pause_btn.setToolTip("Play / Pause")
        self.play_pause_btn.setFixedSize(36, 36)
        self.play_pause_btn.clicked.connect(self._on_play_pause)
        layout.addWidget(self.play_pause_btn)

        # Stop button
        self.stop_btn = QToolButton(self)
        self.stop_btn.setText("\u25A0")  # ■
        self.stop_btn.setToolTip("Stop Narration")
        self.stop_btn.setFixedSize(36, 36)
        self.stop_btn.clicked.connect(self._on_stop)
        layout.addWidget(self.stop_btn)

        # Separator
        layout.addWidget(self._make_separator())

        # Page indicator
        self.page_label = QLabel("Page — / —", self)
        self.page_label.setMinimumWidth(80)
        layout.addWidget(self.page_label)

        # Seek slider
        self.seek_slider = QSlider(Qt.Horizontal, self)
        self.seek_slider.setMinimum(0)
        self.seek_slider.setMaximum(1000)
        self.seek_slider.setValue(0)
        self.seek_slider.setToolTip("Seek within current page")
        self.seek_slider.sliderReleased.connect(self._on_seek)
        layout.addWidget(self.seek_slider, stretch=1)

        # Time label
        self.time_label = QLabel("0:00 / 0:00", self)
        self.time_label.setMinimumWidth(80)
        layout.addWidget(self.time_label)

        # Separator
        layout.addWidget(self._make_separator())

        # Speed control
        speed_label = QLabel("Speed:", self)
        layout.addWidget(speed_label)

        self.speed_combo = QComboBox(self)
        self.speed_combo.addItems(["0.5×", "0.75×", "1.0×", "1.25×", "1.5×", "2.0×"])
        self.speed_combo.setCurrentIndex(2)  # 1.0×
        self.speed_combo.setFixedWidth(65)
        self.speed_combo.currentIndexChanged.connect(self._on_speed_changed)
        layout.addWidget(self.speed_combo)

        # Separator
        layout.addWidget(self._make_separator())

        # Buffering / progress label
        self.status_label = QLabel("", self)
        self.status_label.setStyleSheet("color: #8899AA; font-size: 11px;")
        self.status_label.setMinimumWidth(120)
        layout.addWidget(self.status_label)

        # Auto-scroll toggle
        self.auto_scroll_btn = QToolButton(self)
        self._set_icon(self.auto_scroll_btn, "auto-scroll-icon.png")
        self.auto_scroll_btn.setToolTip("Auto-scroll (on)")
        self.auto_scroll_btn.setCheckable(True)
        self.auto_scroll_btn.setChecked(True)
        self.auto_scroll_btn.setFixedSize(36, 36)
        self.auto_scroll_btn.toggled.connect(self._on_auto_scroll_toggled)
        layout.addWidget(self.auto_scroll_btn)

        # Export button (hidden until narration finishes)
        self.export_btn = QToolButton(self)
        self._set_icon(self.export_btn, "save-icon.png")
        self.export_btn.setToolTip("Export as MP3")
        self.export_btn.setFixedSize(36, 36)
        self.export_btn.clicked.connect(self.export_requested.emit)
        self.export_btn.hide()
        layout.addWidget(self.export_btn)

        # Close button
        self.close_btn = QToolButton(self)
        self.close_btn.setText("\u2715")  # ✕
        self.close_btn.setToolTip("Close")
        self.close_btn.setFixedSize(28, 28)
        self.close_btn.clicked.connect(self._on_stop)
        layout.addWidget(self.close_btn)

    def _make_separator(self) -> QFrame:
        sep = QFrame(self)
        sep.setFrameShape(QFrame.VLine)
        sep.setFrameShadow(QFrame.Sunken)
        sep.setStyleSheet("background-color: #555555; max-width: 1px;")
        return sep

    def _set_icon(self, button: QToolButton, icon_name: str):
        """Load an icon from resources, colour it to match the theme, and apply."""
        from utils.resource_loader import get_icon_path
        path = get_icon_path(icon_name)
        pixmap = QPixmap(path)
        if pixmap.isNull():
            return
        # Colour the icon via the main window helper if available
        main = self.parent()
        if main and hasattr(main, "_color_icon"):
            pixmap = main._color_icon(pixmap)
        button.setIcon(QIcon(pixmap))
        button.setIconSize(QSize(20, 20))

    def refresh_icons(self):
        """Re-colour icons after a theme change."""
        self._set_icon(self.auto_scroll_btn, "auto-scroll-icon.png")
        self._set_icon(self.export_btn, "save-icon.png")

    # ------------------------------------------------------------------
    # Controller binding
    # ------------------------------------------------------------------

    def bind_controller(self, controller):
        """Connect to a NarrationController's signals."""
        self._controller = controller
        controller.playback_started.connect(self._on_playback_started)
        controller.playback_paused.connect(self._on_playback_paused)
        controller.playback_resumed.connect(self._on_playback_resumed)
        controller.playback_stopped.connect(self._on_playback_stopped)
        controller.playback_position_changed.connect(self._on_position_changed)
        controller.buffering.connect(self._on_buffering)
        controller.narration_finished.connect(self._on_narration_finished)
        controller.processing_progress.connect(self._on_processing_progress)
        controller.page_ready.connect(self._on_page_ready)

    # ------------------------------------------------------------------
    # Signal handlers
    # ------------------------------------------------------------------

    def _on_playback_started(self, page_index: int):
        self.show()
        self.raise_()
        self.play_pause_btn.setText("\u275A\u275A")  # ❚❚  (pause icon)
        total = len(self._controller.get_page_order()) if self._controller else 0
        self.page_label.setText(f"Page {page_index + 1} / {total or '?'}")

        # Reset seek slider for new page
        duration = self._controller.get_page_duration(page_index) if self._controller else 0
        self._current_page_duration_ms = duration * 1000
        self.seek_slider.setValue(0)
        self._update_time(0)

    def _on_playback_paused(self):
        self.play_pause_btn.setText("\u25B6")  # ▶

    def _on_playback_resumed(self):
        self.play_pause_btn.setText("\u275A\u275A")  # ❚❚

    def _on_playback_stopped(self):
        self.play_pause_btn.setText("\u25B6")  # ▶
        self.seek_slider.setValue(0)
        self.time_label.setText("0:00 / 0:00")
        self.status_label.setText("")
        self.hide()

    def _on_position_changed(self, page_index: int, position_ms: float):
        if self._current_page_duration_ms > 0:
            ratio = position_ms / self._current_page_duration_ms
            self.seek_slider.blockSignals(True)
            self.seek_slider.setValue(int(ratio * 1000))
            self.seek_slider.blockSignals(False)
        self._update_time(position_ms)

    def _on_buffering(self, is_buffering: bool):
        if is_buffering:
            self.status_label.setText("Buffering next page\u2026")
        else:
            self.status_label.setText("")

    def _on_narration_finished(self, result):
        self.export_btn.show()
        self.status_label.setText("Narration complete")

    def _on_processing_progress(self, current: int, total: int, phase: str):
        if total > 0:
            self.status_label.setText(f"{phase} ({current + 1}/{total})")
        else:
            self.status_label.setText(phase)

    def _on_page_ready(self, page_index: int):
        """Update total page count display as pages arrive."""
        if self._controller:
            total = len(self._controller.get_page_order())
            current_page = self._controller.get_current_page()
            if current_page >= 0:
                self.page_label.setText(f"Page {current_page + 1} / {total}")

    # ------------------------------------------------------------------
    # User actions
    # ------------------------------------------------------------------

    def _on_play_pause(self):
        if self._controller:
            self._controller.toggle_pause()

    def _on_stop(self):
        if self._controller:
            self._controller.stop()
        self.stop_requested.emit()

    def _on_seek(self):
        if self._controller and self._current_page_duration_ms > 0:
            ratio = self.seek_slider.value() / 1000.0
            position_ms = int(ratio * self._current_page_duration_ms)
            self._controller.seek_position(position_ms)

    def _on_speed_changed(self, index: int):
        speeds = [0.5, 0.75, 1.0, 1.25, 1.5, 2.0]
        if self._controller and 0 <= index < len(speeds):
            self._controller.set_playback_speed(speeds[index])

    def _on_auto_scroll_toggled(self, checked: bool):
        self._auto_scroll = checked
        tip = "Auto-scroll (on)" if checked else "Auto-scroll (off)"
        self.auto_scroll_btn.setToolTip(tip)

    @property
    def auto_scroll_enabled(self) -> bool:
        return self._auto_scroll

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _update_time(self, position_ms: float):
        pos_s = int(position_ms / 1000)
        total_s = int(self._current_page_duration_ms / 1000)
        self.time_label.setText(
            f"{pos_s // 60}:{pos_s % 60:02d} / {total_s // 60}:{total_s % 60:02d}"
        )

    def apply_theme(self, dark_mode: bool):
        """Apply theme-appropriate styling."""
        if dark_mode:
            self.setStyleSheet("""
                #NarrationPlayerBar {
                    background-color: #2a2a2a;
                    border-top: 1px solid #444;
                    border-radius: 0px;
                }
                QLabel { color: #ccc; }
                QToolButton {
                    background: transparent;
                    border: 1px solid #555;
                    border-radius: 4px;
                    color: #ccc;
                    font-size: 14px;
                }
                QToolButton:hover { background-color: #444; }
                QToolButton:checked { background-color: #3a6ea5; border-color: #4a9eff; }
                QComboBox {
                    background: #3e3e3e;
                    border: 1px solid #555;
                    border-radius: 4px;
                    color: #ccc;
                    padding: 2px 6px;
                }
                QSlider::groove:horizontal {
                    background: #555;
                    height: 4px;
                    border-radius: 2px;
                }
                QSlider::handle:horizontal {
                    background: #4a9eff;
                    width: 12px;
                    height: 12px;
                    margin: -4px 0;
                    border-radius: 6px;
                }
                QSlider::sub-page:horizontal { background: #4a9eff; }
            """)
        else:
            self.setStyleSheet("""
                #NarrationPlayerBar {
                    background-color: #f5f5f5;
                    border-top: 1px solid #ccc;
                    border-radius: 0px;
                }
                QLabel { color: #333; }
                QToolButton {
                    background: transparent;
                    border: 1px solid #bbb;
                    border-radius: 4px;
                    color: #333;
                    font-size: 14px;
                }
                QToolButton:hover { background-color: #ddd; }
                QToolButton:checked { background-color: #4a9eff; color: white; border-color: #3a8eef; }
                QComboBox {
                    background: white;
                    border: 1px solid #bbb;
                    border-radius: 4px;
                    color: #333;
                    padding: 2px 6px;
                }
                QSlider::groove:horizontal {
                    background: #ccc;
                    height: 4px;
                    border-radius: 2px;
                }
                QSlider::handle:horizontal {
                    background: #4a9eff;
                    width: 12px;
                    height: 12px;
                    margin: -4px 0;
                    border-radius: 6px;
                }
                QSlider::sub-page:horizontal { background: #4a9eff; }
            """)
