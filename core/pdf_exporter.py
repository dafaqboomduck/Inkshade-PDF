import fitz  # PyMuPDF
from helpers.annotations import AnnotationType, Annotation
from typing import List

class PDFExporter:
    """Handles exporting annotations to PDF files."""
    
    @staticmethod
    def export_annotations_to_pdf(source_pdf_path: str, output_pdf_path: str, annotations: List[Annotation]) -> bool:
        """
        Export annotations to a PDF file.
        
        Args:
            source_pdf_path: Path to the original PDF
            output_pdf_path: Path where the annotated PDF should be saved
            annotations: List of annotations to add to the PDF
            
        Returns:
            True if successful, False otherwise
        """
        try:
            # Open the PDF
            doc = fitz.open(source_pdf_path)
            
            # Group annotations by page for efficiency
            annotations_by_page = {}
            for ann in annotations:
                if ann.page_index not in annotations_by_page:
                    annotations_by_page[ann.page_index] = []
                annotations_by_page[ann.page_index].append(ann)
            
            # Add annotations to each page
            for page_idx, page_annotations in annotations_by_page.items():
                if page_idx >= len(doc):
                    continue
                    
                page = doc[page_idx]
                
                for ann in page_annotations:
                    try:
                        PDFExporter._add_annotation_to_page(page, ann)
                    except Exception as e:
                        print(f"Failed to add annotation on page {page_idx}: {e}")
                        continue
            
            # Save the modified PDF
            doc.save(output_pdf_path, garbage=4, deflate=True)
            doc.close()
            
            return True
            
        except Exception as e:
            print(f"Failed to export annotations to PDF: {e}")
            return False
    
    @staticmethod
    def _add_annotation_to_page(page: fitz.Page, annotation: Annotation):
        """Add a single annotation to a PDF page."""
        
        if annotation.annotation_type == AnnotationType.HIGHLIGHT:
            # Add highlight annotations
            for quad in annotation.quads:
                # Convert quad format [x0, y0, x1, y1, x2, y2, x3, y3] to fitz.Rect
                rect = fitz.Rect(quad[0], quad[1], quad[2], quad[5])
                color = [c / 255.0 for c in annotation.color]  # PyMuPDF uses 0-1 range
                
                highlight = page.add_highlight_annot(rect)
                highlight.set_colors(stroke=color)
                highlight.update()
        
        elif annotation.annotation_type == AnnotationType.UNDERLINE:
            # Add underline annotations
            for quad in annotation.quads:
                rect = fitz.Rect(quad[0], quad[1], quad[2], quad[5])
                color = [c / 255.0 for c in annotation.color]
                
                underline = page.add_underline_annot(rect)
                underline.set_colors(stroke=color)
                underline.update()
        
        elif annotation.annotation_type == AnnotationType.FREEHAND:
            # Add freehand drawing (ink annotation)
            if annotation.points and len(annotation.points) >= 2:
                # PyMuPDF expects: list of strokes, each stroke is a list of points
                # Each point must be a fitz.Point object
                stroke = [fitz.Point(float(p[0]), float(p[1])) for p in annotation.points]
                ink_list = [stroke]  # Wrap in list as it expects multiple strokes
                
                color = [c / 255.0 for c in annotation.color]
                
                ink = page.add_ink_annot(ink_list)
                ink.set_colors(stroke=color)
                ink.set_border(width=annotation.stroke_width)
                ink.update()
                
                # For filled freehand, draw as shape
                if annotation.filled and len(annotation.points) >= 3:
                    points = [fitz.Point(float(p[0]), float(p[1])) for p in annotation.points]
                    # Close the shape by adding first point at the end
                    if points[0] != points[-1]:
                        points.append(points[0])
                    
                    shape = page.new_shape()
                    shape.draw_polyline(points)
                    shape.finish(color=color, fill=color, width=annotation.stroke_width)
                    shape.commit()
        
        elif annotation.annotation_type == AnnotationType.LINE:
            # Add line annotation
            if annotation.points and len(annotation.points) >= 2:
                start = annotation.points[0]
                end = annotation.points[-1]
                color = [c / 255.0 for c in annotation.color]
                
                line = page.add_line_annot(
                    fitz.Point(float(start[0]), float(start[1])), 
                    fitz.Point(float(end[0]), float(end[1]))
                )
                line.set_colors(stroke=color)
                line.set_border(width=annotation.stroke_width)
                line.update()
        
        elif annotation.annotation_type == AnnotationType.ARROW:
            # Add line with arrow
            if annotation.points and len(annotation.points) >= 2:
                start = annotation.points[0]
                end = annotation.points[-1]
                color = [c / 255.0 for c in annotation.color]
                
                # PyMuPDF line annotation with arrow ending
                line = page.add_line_annot(
                    fitz.Point(float(start[0]), float(start[1])), 
                    fitz.Point(float(end[0]), float(end[1]))
                )
                line.set_colors(stroke=color)
                line.set_border(width=annotation.stroke_width)
                line.line_ends = (0, 2)  # 0=None at start, 2=Arrow at end
                line.update()
        
        elif annotation.annotation_type == AnnotationType.RECTANGLE:
            # Add rectangle annotation
            if annotation.points and len(annotation.points) >= 2:
                start = annotation.points[0]
                end = annotation.points[-1]
                
                x0, y0 = min(float(start[0]), float(end[0])), min(float(start[1]), float(end[1]))
                x1, y1 = max(float(start[0]), float(end[0])), max(float(start[1]), float(end[1]))
                rect = fitz.Rect(x0, y0, x1, y1)
                
                color = [c / 255.0 for c in annotation.color]
                
                square = page.add_rect_annot(rect)
                if annotation.filled:
                    square.set_colors(stroke=color, fill=color)
                else:
                    square.set_colors(stroke=color)
                
                square.set_border(width=annotation.stroke_width)
                square.update()
        
        elif annotation.annotation_type == AnnotationType.CIRCLE:
            # Add circle/ellipse annotation
            if annotation.points and len(annotation.points) >= 2:
                start = annotation.points[0]
                end = annotation.points[-1]
                
                x0, y0 = min(float(start[0]), float(end[0])), min(float(start[1]), float(end[1]))
                x1, y1 = max(float(start[0]), float(end[0])), max(float(start[1]), float(end[1]))
                rect = fitz.Rect(x0, y0, x1, y1)
                
                color = [c / 255.0 for c in annotation.color]
                
                circle = page.add_circle_annot(rect)
                if annotation.filled:
                    circle.set_colors(stroke=color, fill=color)
                else:
                    circle.set_colors(stroke=color)
                
                circle.set_border(width=annotation.stroke_width)
                circle.update()