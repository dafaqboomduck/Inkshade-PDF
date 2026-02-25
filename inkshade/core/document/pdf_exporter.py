import fitz  # PyMuPDF
from inkshade.core.annotations import AnnotationType, Annotation
from typing import List
from PyQt5.QtCore import QObject, pyqtSignal

class PDFExporter(QObject):
    """Handles exporting annotations to PDF files."""
    
    # Signal for progress updates (optional, can be None)
    progress_signal = pyqtSignal(int, int)  # current, total
    
    def __init__(self):
        super().__init__()
    
    def export_annotations_to_pdf(self, source_pdf_path: str, output_pdf_path: str, annotations: List[Annotation]) -> bool:
        """
        Export annotations to a PDF file with progress updates.
        
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
            
            total_pages = len(annotations_by_page)
            current_page = 0
            
            # Add annotations to each page
            for page_idx, page_annotations in annotations_by_page.items():
                if page_idx >= len(doc):
                    continue
                
                # Emit progress
                try:
                    self.progress_signal.emit(current_page, total_pages)
                except:
                    pass  # Signal not connected, ignore
                
                page = doc[page_idx]
                
                for ann in page_annotations:
                    self._add_annotation_to_page(page, ann)
                
                current_page += 1
            
            # Emit final progress
            try:
                self.progress_signal.emit(total_pages, total_pages)
            except:
                pass
            
            # Save the modified PDF
            doc.save(output_pdf_path, garbage=4, deflate=True)
            doc.close()
            
            return True
            
        except Exception as e:
            print(f"Failed to export annotations to PDF: {e}")
            return False
    
    def _add_annotation_to_page(self, page: fitz.Page, annotation: Annotation):
        """Add a single annotation to a PDF page."""
        
        try:
            if annotation.annotation_type == AnnotationType.HIGHLIGHT:
                # Add highlight annotations
                for quad in annotation.quads:
                    # Convert quad format [x0, y0, x1, y1, x2, y2, x3, y3] to fitz.Quad
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
                    # Convert points to PyMuPDF format - must be list of lists of tuples/Points
                    # Each inner list is a separate stroke
                    ink_list = [[(float(p[0]), float(p[1])) for p in annotation.points]]
                    color = [c / 255.0 for c in annotation.color]
                    
                    ink = page.add_ink_annot(ink_list)
                    ink.set_colors(stroke=color)
                    ink.set_border(width=annotation.stroke_width)
                    
                    # Fill if requested (use shape drawing instead)
                    if annotation.filled:
                        points = [fitz.Point(p[0], p[1]) for p in annotation.points]
                        shape = page.new_shape()
                        shape.draw_polyline(points)
                        shape.finish(color=color, fill=color, width=annotation.stroke_width)
                        shape.commit()
                    
                    ink.update()
        
                    
            elif annotation.annotation_type == AnnotationType.LINE:
                # Add line annotation using shape drawing for better control
                if annotation.points and len(annotation.points) >= 2:
                    start = annotation.points[0]
                    end = annotation.points[-1]
                    color = [c / 255.0 for c in annotation.color]
                    
                    shape = page.new_shape()
                    shape.draw_line(fitz.Point(start[0], start[1]), fitz.Point(end[0], end[1]))
                    shape.finish(color=color, width=annotation.stroke_width)
                    shape.commit()
            
            elif annotation.annotation_type == AnnotationType.ARROW:
                # Add arrow using shape drawing
                if annotation.points and len(annotation.points) >= 2:
                    import math
                    start = annotation.points[0]
                    end = annotation.points[-1]
                    color = [c / 255.0 for c in annotation.color]
                    
                    # Calculate arrow head parameters
                    arrow_size = 10 * (annotation.stroke_width / 2.0)
                    dx = end[0] - start[0]
                    dy = end[1] - start[1]
                    length = math.sqrt(dx*dx + dy*dy)
                    
                    if length > 0:
                        # Normalize direction
                        dx_norm = dx / length
                        dy_norm = dy / length
                        
                        # Shorten the main line so it stops before the arrowhead
                        line_end_x = end[0] - dx_norm * arrow_size * 0.5
                        line_end_y = end[1] - dy_norm * arrow_size * 0.5
                        
                        angle = math.atan2(dy, dx)
                        
                        shape = page.new_shape()
                        
                        # Draw the main line (shortened)
                        shape.draw_line(fitz.Point(start[0], start[1]), fitz.Point(line_end_x, line_end_y))
                        
                        # Draw arrow head
                        arrow_p1 = fitz.Point(
                            end[0] - arrow_size * math.cos(angle - math.pi / 6),
                            end[1] - arrow_size * math.sin(angle - math.pi / 6)
                        )
                        arrow_p2 = fitz.Point(
                            end[0] - arrow_size * math.cos(angle + math.pi / 6),
                            end[1] - arrow_size * math.sin(angle + math.pi / 6)
                        )
                        
                        shape.draw_line(arrow_p1, fitz.Point(end[0], end[1]))
                        shape.draw_line(arrow_p2, fitz.Point(end[0], end[1]))
                        
                        shape.finish(color=color, width=annotation.stroke_width)
                        shape.commit()
            
            elif annotation.annotation_type == AnnotationType.RECTANGLE:
                # Add rectangle annotation
                if annotation.points and len(annotation.points) >= 2:
                    start = annotation.points[0]
                    end = annotation.points[-1]
                    
                    x0, y0 = min(start[0], end[0]), min(start[1], end[1])
                    x1, y1 = max(start[0], end[0]), max(start[1], end[1])
                    rect = fitz.Rect(x0, y0, x1, y1)
                    
                    color = [c / 255.0 for c in annotation.color]
                    
                    if annotation.filled:
                        square = page.add_rect_annot(rect)
                        square.set_colors(stroke=color, fill=color)
                    else:
                        square = page.add_rect_annot(rect)
                        square.set_colors(stroke=color)
                    
                    square.set_border(width=annotation.stroke_width)
                    square.update()
            
            elif annotation.annotation_type == AnnotationType.CIRCLE:
                # Add circle/ellipse annotation
                if annotation.points and len(annotation.points) >= 2:
                    start = annotation.points[0]
                    end = annotation.points[-1]
                    
                    x0, y0 = min(start[0], end[0]), min(start[1], end[1])
                    x1, y1 = max(start[0], end[0]), max(start[1], end[1])
                    rect = fitz.Rect(x0, y0, x1, y1)
                    
                    color = [c / 255.0 for c in annotation.color]
                    
                    if annotation.filled:
                        circle = page.add_circle_annot(rect)
                        circle.set_colors(stroke=color, fill=color)
                    else:
                        circle = page.add_circle_annot(rect)
                        circle.set_colors(stroke=color)
                    
                    circle.set_border(width=annotation.stroke_width)
                    circle.update()
                    
        except Exception as e:
            print(f"Failed to add annotation on page {annotation.page_index}: {e}")