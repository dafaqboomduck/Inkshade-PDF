from typing import List
import json

from helpers.annotations import AnnotationType, Annotation

class AnnotationManager:
    """Manages all annotations for a PDF document."""

    def __init__(self):
        self.annotations: List[Annotation] = []
        self.pdf_path = None

    def add_annotation(self, annotation: Annotation):
        """Add a new annotation"""
        self.annotations.append(annotation)

    def get_annotations_for_page(self, page_index: int) -> List[Annotation]:
        """Get all annotations for a specific page"""
        return [ann for ann in self.annotations if ann.page_index == page_index]
    
    def remove_annotation(self, annotation: Annotation):
        """Remove an annotation"""
        if annotation in self.annotations:
            self.annotations.remove(annotation)
    
    def clear_all(self):
        """Clear all annotations"""
        self.annotations.clear()

    def save_to_json(self, file_path: str):
        """Save annotations to a JSON file."""
        data = {
            'pdf_path': self.pdf_path,
            'annotations': [ann.to_dict() for ann in self.annotations]
        }
        with open(file_path, 'w') as f:
            json.dump(data, f, indent=2)
    
    def load_from_json(self, file_path: str):
        """Load annotations from a JSON file."""
        with open(file_path, 'r') as f:
            data = json.load(f)
        
        self.pdf_path = data.get('pdf_path')
        self.annotations = [Annotation.from_dict(ann_data) for ann_data in data['annotations']]
    
    def get_annotation_count(self) -> int:
        """Get total number of annotations."""
        return len(self.annotations)