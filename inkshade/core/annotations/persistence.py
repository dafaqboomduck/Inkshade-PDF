"""
Handles persistence of annotations to/from JSON files.
"""
import json
import os
import hashlib
from typing import List, Optional, Tuple
from .models import Annotation


class AnnotationPersistence:
    """Manages saving and loading annotations to/from disk."""
    
    def __init__(self):
        self._app_data_dir: Optional[str] = None
    
    def get_app_data_dir(self) -> str:
        """
        Get or create the app's data directory for storing annotations.
        
        Returns:
            Path to the annotations directory
        """
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
    
    def get_json_path(self, pdf_path: str) -> str:
        """
        Get the JSON file path for a given PDF.
        
        Args:
            pdf_path: Path to the PDF file
            
        Returns:
            Path to the corresponding JSON annotations file
        """
        # Create a hash of the PDF path to use as filename
        # This ensures unique storage per PDF regardless of location
        path_hash = hashlib.md5(pdf_path.encode()).hexdigest()
        
        # Store JSON in app data directory with hashed filename
        app_dir = self.get_app_data_dir()
        return os.path.join(app_dir, f"{path_hash}.json")
    
    def save_to_json(self, annotations: List[Annotation], pdf_path: str, 
                     file_path: Optional[str] = None) -> bool:
        """
        Save annotations to a JSON file.
        
        Args:
            annotations: List of annotations to save
            pdf_path: Path to the associated PDF
            file_path: Optional custom path for the JSON file
            
        Returns:
            True if save was successful, False otherwise
        """
        if file_path is None:
            file_path = self.get_json_path(pdf_path)
        
        try:
            data = {
                'pdf_path': pdf_path,
                'annotations': [ann.to_dict() for ann in annotations]
            }
            
            # Ensure directory exists
            os.makedirs(os.path.dirname(file_path), exist_ok=True)
            
            with open(file_path, 'w') as f:
                json.dump(data, f, indent=2)
            return True
        except Exception as e:
            print(f"Failed to save annotations: {e}")
            return False
    
    def load_from_json(self, pdf_path: str, 
                       file_path: Optional[str] = None) -> Tuple[List[Annotation], bool]:
        """
        Load annotations from a JSON file.
        
        Args:
            pdf_path: Path to the PDF file
            file_path: Optional custom path for the JSON file
            
        Returns:
            Tuple of (list of annotations, success flag)
        """
        if file_path is None:
            file_path = self.get_json_path(pdf_path)
        
        if not os.path.exists(file_path):
            return [], False
        
        try:
            with open(file_path, 'r') as f:
                data = json.load(f)
            
            # Verify this is for the correct PDF
            stored_pdf_path = data.get('pdf_path')
            if stored_pdf_path != pdf_path:
                print(f"Warning: JSON file is for different PDF: {stored_pdf_path}")
            
            annotations = [Annotation.from_dict(ann_data) 
                          for ann_data in data.get('annotations', [])]
            return annotations, True
        except Exception as e:
            print(f"Failed to load annotations: {e}")
            return [], False
    
    def delete_json_file(self, pdf_path: str) -> bool:
        """
        Delete the JSON annotation file for a PDF.
        
        Args:
            pdf_path: Path to the PDF file
            
        Returns:
            True if deletion was successful or file didn't exist
        """
        file_path = self.get_json_path(pdf_path)
        
        if not os.path.exists(file_path):
            return True
        
        try:
            os.remove(file_path)
            return True
        except Exception as e:
            print(f"Failed to delete JSON file: {e}")
            return False
    
    def has_saved_annotations(self, pdf_path: str) -> bool:
        """
        Check if saved annotations exist for a PDF.
        
        Args:
            pdf_path: Path to the PDF file
            
        Returns:
            True if a JSON file exists for this PDF
        """
        return os.path.exists(self.get_json_path(pdf_path))