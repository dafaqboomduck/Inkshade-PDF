# core/export_worker.py

from PyQt5.QtCore import QThread, pyqtSignal
from core.document.pdf_exporter import PDFExporter
import tempfile
import shutil
import os


class ExportWorker(QThread):
    """Worker thread for exporting annotations to PDF without freezing the UI."""
    
    # Signals
    finished = pyqtSignal(bool, str)  # success, message
    progress = pyqtSignal(str)  # status message
    page_progress = pyqtSignal(int, int)  # current, total pages
    
    def __init__(self, source_pdf, output_pdf, annotations, use_temp_file=False):
        super().__init__()
        self.source_pdf = source_pdf
        self.output_pdf = output_pdf
        self.annotations = annotations
        self.use_temp_file = use_temp_file
        self.temp_path = None
        self.exporter = PDFExporter()
    
    def run(self):
        """Execute the export in a background thread."""
        try:
            # Connect exporter progress to our signal
            self.exporter.progress_signal.connect(self._on_page_progress)
            
            if self.use_temp_file:
                # Create temp file in same directory
                output_dir = os.path.dirname(self.output_pdf)
                temp_fd, self.temp_path = tempfile.mkstemp(suffix='.pdf', dir=output_dir)
                os.close(temp_fd)
                
                self.progress.emit("Exporting annotations...")
                
                # Export to temp file
                success = self.exporter.export_annotations_to_pdf(
                    self.source_pdf,
                    self.temp_path,
                    self.annotations
                )
                
                if success:
                    self.progress.emit("Finalizing...")
                    # Replace original with temp file
                    shutil.move(self.temp_path, self.output_pdf)
                    self.finished.emit(True, "Annotations saved successfully to PDF!")
                else:
                    # Clean up temp file on failure
                    if os.path.exists(self.temp_path):
                        os.remove(self.temp_path)
                    self.finished.emit(False, "Failed to export annotations to PDF.")
            else:
                # Direct export to different file
                self.progress.emit("Exporting annotations...")
                
                success = self.exporter.export_annotations_to_pdf(
                    self.source_pdf,
                    self.output_pdf,
                    self.annotations
                )
                
                if success:
                    self.finished.emit(True, "Annotations saved successfully to PDF!")
                else:
                    self.finished.emit(False, "Failed to export annotations to PDF.")
                    
        except Exception as e:
            # Clean up temp file if it exists
            if self.temp_path and os.path.exists(self.temp_path):
                os.remove(self.temp_path)
            self.finished.emit(False, f"Error during export: {str(e)}")
    
    def _on_page_progress(self, current, total):
        """Handle page-level progress updates."""
        self.page_progress.emit(current, total)