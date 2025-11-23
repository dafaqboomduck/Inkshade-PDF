from typing import List
import json
import os
import hashlib

from helpers.annotations import AnnotationType, Annotation

class AnnotationManager:
    """Manages all annotations for a PDF document."""

    def __init__(self):
        self.annotations: List[Annotation] = []
        self.pdf_path = None
        self.has_unsaved_changes = False
        self.json_file_path = None
        self._app_data_dir = None

    def _get_app_data_dir(self):
        """Get or create the app's data directory for storing annotations."""
        if self._app_data_dir:
            return self._app_data_dir
            
        # Use user's app data directory
        if os.name == 'nt':  # Windows
            base_dir = os.environ.get('APPDATA', os.path.expanduser('~'))
        else:  # macOS, Linux
            base_dir = os.path.expanduser('~/.local/share')
        
        app_dir = os.path.join(base_dir, 'InkshadePDF', 'annotations')
        os.makedirs(app_dir, exist_ok=True)
        self._app_data_dir = app_dir
        return app_dir

    def set_pdf_path(self, pdf_path: str):
        """Set the current PDF path and determine JSON file location."""
        self.pdf_path = pdf_path
        
        # Create a hash of the PDF path to use as filename
        # This ensures unique storage per PDF regardless of location
        path_hash = hashlib.md5(pdf_path.encode()).hexdigest()
        
        # Store JSON in app data directory with hashed filename
        app_dir = self._get_app_data_dir()
        self.json_file_path = os.path.join(app_dir, f"{path_hash}.json")
        
    def add_annotation(self, annotation: Annotation):
        """Add a new annotation and mark as having unsaved changes."""
        self.annotations.append(annotation)
        self.has_unsaved_changes = True
        self._auto_save()

    def get_annotations_for_page(self, page_index: int) -> List[Annotation]:
        """Get all annotations for a specific page"""
        return [ann for ann in self.annotations if ann.page_index == page_index]
    
    def remove_annotation(self, annotation: Annotation):
        """Remove an annotation and mark as having unsaved changes."""
        if annotation in self.annotations:
            self.annotations.remove(annotation)
            self.has_unsaved_changes = True
            self._auto_save()
    
    def clear_all(self):
        """Clear all annotations"""
        self.annotations.clear()
        self.has_unsaved_changes = False
        self.pdf_path = None
        self.json_file_path = None

    def _auto_save(self):
        """Automatically save annotations to JSON file."""
        if self.json_file_path:
            try:
                self.save_to_json(self.json_file_path)
            except Exception as e:
                print(f"Auto-save failed: {e}")

    def save_to_json(self, file_path: str = None):
        """Save annotations to a JSON file."""
        if file_path is None:
            file_path = self.json_file_path
            
        if not file_path:
            return
            
        data = {
            'pdf_path': self.pdf_path,
            'annotations': [ann.to_dict() for ann in self.annotations]
        }
        with open(file_path, 'w') as f:
            json.dump(data, f, indent=2)
    
    def load_from_json(self, file_path: str = None):
        """Load annotations from a JSON file."""
        if file_path is None:
            file_path = self.json_file_path
            
        if not file_path or not os.path.exists(file_path):
            return False
            
        try:
            with open(file_path, 'r') as f:
                data = json.load(f)
            
            self.pdf_path = data.get('pdf_path')
            self.annotations = [Annotation.from_dict(ann_data) for ann_data in data['annotations']]
            self.has_unsaved_changes = False
            return True
        except Exception as e:
            print(f"Failed to load annotations: {e}")
            return False
    
    def auto_load_annotations(self):
        """Try to automatically load annotations for the current PDF."""
        if self.json_file_path and os.path.exists(self.json_file_path):
            return self.load_from_json()
        return False
    
    def delete_json_file(self):
        """Delete the JSON annotation file."""
        if self.json_file_path and os.path.exists(self.json_file_path):
            try:
                os.remove(self.json_file_path)
                self.has_unsaved_changes = False
            except Exception as e:
                print(f"Failed to delete JSON file: {e}")
    
    def mark_saved(self):
        """Mark all changes as saved."""
        self.has_unsaved_changes = False
    
    def get_annotation_count(self) -> int:
        """Get total number of annotations."""
        return len(self.annotations)