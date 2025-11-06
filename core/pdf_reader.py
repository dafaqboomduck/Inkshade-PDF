import fitz  # PyMuPDF
from PyQt5.QtGui import QImage, QPixmap, QPainterPath
from PyQt5.QtCore import QRectF, QPointF
from PyQt5.QtWidgets import QMessageBox
from typing import List, Tuple, Optional, Dict
from helpers.pdf_elements import (TextElement, ImageElement, 
                                  VectorElement, LinkElement, PageElements)

class PDFDocumentReader:
    def __init__(self):
        self.doc = None
        self.total_pages = 0
        self.search_results = []
        self.current_search_index = -1
        self.current_search_term = ""
        self.toc = []
        
        # Cache for parsed page elements
        self._page_elements_cache: Dict[int, PageElements] = {}
        
    def load_pdf(self, file_path):
        """Loads a PDF document and returns the number of pages."""
        try:
            self.doc = fitz.open(file_path)
            self.total_pages = self.doc.page_count
            self._clear_search()
            self._page_elements_cache.clear()
            
            # Get detailed TOC with positioning info
            self.toc = self.doc.get_toc(False)
            
            return True, self.total_pages
        except Exception as e:
            QMessageBox.critical(None, "Error", f"Error loading PDF: {e}")
            return False, 0
    
    def close_document(self):
        """Closes the current PDF document and clears all state."""
        if self.doc:
            self.doc.close()
            self.doc = None
        self.total_pages = 0
        self._clear_search()
        self._page_elements_cache.clear()
    
    def render_page(self, page_index: int, zoom_level: float, dark_mode: bool):
        """
        Renders a page to a QPixmap using PyMuPDF's rendering engine.
        This ensures accurate text rendering.
        """
        if not self.doc or page_index >= self.total_pages:
            return None
        
        try:
            page = self.doc.load_page(page_index)
            
            # Create transformation matrix for zoom
            mat = fitz.Matrix(zoom_level, zoom_level)
            
            # Render page to pixmap
            pix = page.get_pixmap(matrix=mat, alpha=False)
            
            # Convert to QImage
            img = QImage(pix.samples, pix.width, pix.height, pix.stride, QImage.Format_RGB888)
            
            # Apply dark mode if needed
            if dark_mode:
                img.invertPixels()
            
            # Convert to QPixmap
            pixmap = QPixmap.fromImage(img)
            
            return pixmap
            
        except Exception as e:
            print(f"Error rendering page {page_index+1}: {e}")
            return None
    
    def get_page_elements(self, page_index: int, use_cache: bool = True) -> Optional[PageElements]:
        """
        Extracts and returns all elements from a page.
        
        Args:
            page_index: Zero-based page index
            use_cache: Whether to use cached elements if available
            
        Returns:
            PageElements object containing all parsed elements
        """
        if not self.doc or page_index >= self.total_pages:
            return None
        
        # Check cache first
        if use_cache and page_index in self._page_elements_cache:
            return self._page_elements_cache[page_index]
        
        try:
            page = self.doc.load_page(page_index)
            
            # Extract elements
            texts = self._extract_text_elements(page, page_index)
            images = self._extract_image_elements(page, page_index)
            vectors = self._extract_vector_elements(page, page_index)
            links = self._extract_link_elements(page, page_index)
            
            page_rect = page.rect
            elements = PageElements(
                texts=texts,
                images=images,
                vectors=vectors,
                links=links,
                width=page_rect.width,
                height=page_rect.height
            )
            
            # Cache the result
            self._page_elements_cache[page_index] = elements
            
            return elements
            
        except Exception as e:
            print(f"Error parsing page {page_index+1}: {e}")
            import traceback
            traceback.print_exc()
            return None
    
    def _extract_text_elements(self, page: fitz.Page, page_index: int) -> List[TextElement]:
        """Extract text as spans (word groups) with character-level data for selection."""
        text_elements = []
        
        try:
            # Use dict mode to get reliable span-level text
            blocks = page.get_text("dict", flags=fitz.TEXT_PRESERVE_WHITESPACE)
            
            for block in blocks.get("blocks", []):
                if block.get("type") != 0:  # Not a text block
                    continue
                
                for line in block.get("lines", []):
                    for span in line.get("spans", []):
                        text = span.get("text", "")
                        if not text or not text.strip():
                            continue
                        
                        font_name = span.get("font", "")
                        font_size = span.get("size", 12)
                        color_int = span.get("color", 0)
                        bbox = span.get("bbox", (0, 0, 0, 0))
                        origin = span.get("origin", (bbox[0], bbox[3]))  # Baseline position
                        
                        # Convert color from integer to RGB
                        color = (
                            (color_int >> 16) & 0xFF,
                            (color_int >> 8) & 0xFF,
                            color_int & 0xFF
                        )
                        
                        # Get character-level data for this span (for selection)
                        chars_data = []
                        chars_list = span.get("chars", [])
                        
                        if chars_list:
                            # Use actual character positions
                            for char_info in chars_list:
                                char = char_info.get("c", "")
                                char_bbox = char_info.get("bbox", (0, 0, 0, 0))
                                chars_data.append((char, char_bbox))
                        else:
                            # Fallback: estimate character positions
                            char_width = (bbox[2] - bbox[0]) / len(text) if len(text) > 0 else 0
                            for i, char in enumerate(text):
                                char_x0 = bbox[0] + (i * char_width)
                                char_x1 = char_x0 + char_width
                                char_bbox = (char_x0, bbox[1], char_x1, bbox[3])
                                chars_data.append((char, char_bbox))
                        
                        # Create text element for the entire span
                        text_elem = TextElement(
                            text=text,
                            bbox=bbox,
                            font_name=font_name,
                            font_size=font_size,
                            color=color,
                            page_index=page_index,
                            chars=chars_data
                        )
                        text_elements.append(text_elem)
        
        except Exception as e:
            print(f"Error extracting text elements: {e}")
            import traceback
            traceback.print_exc()
        
        return text_elements
    
    def _extract_image_elements(self, page: fitz.Page, page_index: int) -> List[ImageElement]:
        """Extract embedded images from the page."""
        image_elements = []
        
        try:
            image_list = page.get_images(full=True)
            
            for img_index, img in enumerate(image_list):
                xref = img[0]
                
                # Get image bbox
                rects = page.get_image_rects(xref)
                
                if not rects:
                    continue
                
                # Get the actual image
                base_image = self.doc.extract_image(xref)
                image_bytes = base_image["image"]
                
                # Convert to QPixmap
                qimg = QImage.fromData(image_bytes)
                pixmap = QPixmap.fromImage(qimg)
                
                for rect in rects:
                    bbox = (rect.x0, rect.y0, rect.x1, rect.y1)
                    
                    img_elem = ImageElement(
                        bbox=bbox,
                        pixmap=pixmap,
                        page_index=page_index,
                        transform=list(rect)
                    )
                    image_elements.append(img_elem)
        
        except Exception as e:
            print(f"Error extracting images: {e}")
        
        return image_elements
    
    def _extract_vector_elements(self, page: fitz.Page, page_index: int) -> List[VectorElement]:
        """Extract vector graphics (paths, lines, shapes) from the page."""
        vector_elements = []
        
        try:
            # Get drawing commands
            paths = page.get_drawings()
            
            for path_dict in paths:
                qpath = QPainterPath()
                
                # Convert path items to QPainterPath
                for item in path_dict.get("items", []):
                    item_type = item[0]
                    
                    if item_type == "l":  # Line
                        p1, p2 = item[1], item[2]
                        qpath.moveTo(QPointF(p1.x, p1.y))
                        qpath.lineTo(QPointF(p2.x, p2.y))
                    
                    elif item_type == "c":  # Curve
                        p1, p2, p3, p4 = item[1], item[2], item[3], item[4]
                        qpath.moveTo(QPointF(p1.x, p1.y))
                        qpath.cubicTo(
                            QPointF(p2.x, p2.y),
                            QPointF(p3.x, p3.y),
                            QPointF(p4.x, p4.y)
                        )
                    
                    elif item_type == "re":  # Rectangle
                        rect = item[1]
                        qpath.addRect(QRectF(rect.x0, rect.y0, rect.width, rect.height))
                    
                    elif item_type == "qu":  # Quad
                        quad = item[1]
                        qpath.moveTo(QPointF(quad.ul.x, quad.ul.y))
                        qpath.lineTo(QPointF(quad.ur.x, quad.ur.y))
                        qpath.lineTo(QPointF(quad.lr.x, quad.lr.y))
                        qpath.lineTo(QPointF(quad.ll.x, quad.ll.y))
                        qpath.closeSubpath()
                
                # Get colors
                stroke_color = None
                fill_color = None
                
                if "color" in path_dict and path_dict["color"]:
                    color_vals = path_dict["color"]
                    stroke_color = (
                        int(color_vals[0] * 255),
                        int(color_vals[1] * 255),
                        int(color_vals[2] * 255)
                    )
                
                if "fill" in path_dict and path_dict["fill"]:
                    fill_vals = path_dict["fill"]
                    fill_color = (
                        int(fill_vals[0] * 255),
                        int(fill_vals[1] * 255),
                        int(fill_vals[2] * 255)
                    )
                
                line_width = path_dict.get("width", 1.0)
                
                vector_elem = VectorElement(
                    path=qpath,
                    stroke_color=stroke_color,
                    fill_color=fill_color,
                    line_width=line_width,
                    page_index=page_index
                )
                vector_elements.append(vector_elem)
        
        except Exception as e:
            print(f"Error extracting vector elements: {e}")
        
        return vector_elements
    
    def _extract_link_elements(self, page: fitz.Page, page_index: int) -> List[LinkElement]:
        """Extract clickable links from the page."""
        link_elements = []
        
        try:
            links = page.get_links()
            
            for link in links:
                bbox = link.get("from", (0, 0, 0, 0))
                link_type = link.get("kind", 0)
                
                # Map link type
                type_map = {
                    1: "goto",    # Internal link
                    2: "uri",     # External URI
                    3: "gotor",   # Go to other document
                    4: "launch",  # Launch application
                    5: "named"    # Named action
                }
                
                link_type_str = type_map.get(link_type, "unknown")
                
                # Get destination
                destination = None
                if link_type_str == "goto":
                    destination = link.get("page", None)
                elif link_type_str == "uri":
                    destination = link.get("uri", "")
                
                link_elem = LinkElement(
                    bbox=bbox,
                    link_type=link_type_str,
                    destination=destination,
                    page_index=page_index
                )
                link_elements.append(link_elem)
        
        except Exception as e:
            print(f"Error extracting links: {e}")
        
        return link_elements
    
    def get_text_at_position(self, page_index: int, x: float, y: float, 
                            tolerance: float = 2.0) -> Optional[TextElement]:
        """
        Get the text span at a specific position on the page.
        """
        elements = self.get_page_elements(page_index)
        if not elements:
            return None
        
        for text_elem in elements.texts:
            bbox = text_elem.bbox
            if (bbox[0] - tolerance <= x <= bbox[2] + tolerance and
                bbox[1] - tolerance <= y <= bbox[3] + tolerance):
                return text_elem
        
        return None
    
    def get_link_at_position(self, page_index: int, x: float, y: float) -> Optional[LinkElement]:
        """Get the link at a specific position on the page."""
        elements = self.get_page_elements(page_index)
        if not elements:
            return None
        
        for link_elem in elements.links:
            bbox = link_elem.bbox
            if bbox[0] <= x <= bbox[2] and bbox[1] <= y <= bbox[3]:
                return link_elem
        
        return None
    
    def _clear_search(self):
        """Resets the search state."""
        self.search_results = []
        self.current_search_index = -1
        self.current_search_term = ""
    
    def execute_search(self, search_term: str) -> int:
        """Performs a search across the entire document."""
        if not search_term:
            self._clear_search()
            return 0
        
        if search_term != self.current_search_term:
            self.current_search_term = search_term
            self.search_results = []
            
            # Search using PyMuPDF's built-in search
            for i in range(self.total_pages):
                page = self.doc.load_page(i)
                quads_on_page = page.search_for(search_term, quads=True)
                
                for quad in quads_on_page:
                    self.search_results.append((i, quad.rect))
            
            self.current_search_index = -1
        
        return len(self.search_results)
    
    def get_toc(self):
        """Returns the parsed table of contents."""
        return self.toc
    
    def next_search_result(self):
        """Moves to the next search result."""
        if not self.search_results:
            return None, None
        self.current_search_index = (self.current_search_index + 1) % len(self.search_results)
        return self.search_results[self.current_search_index]
    
    def prev_search_result(self):
        """Moves to the previous search result."""
        if not self.search_results:
            return None, None
        self.current_search_index = (self.current_search_index - 1 + len(self.search_results)) % len(self.search_results)
        return self.search_results[self.current_search_index]
    
    def get_search_result_info(self):
        """Returns current search result info."""
        if self.current_search_index == -1:
            return None, None
        return self.search_results[self.current_search_index]
    
    def get_all_search_results(self):
        """Returns all search results."""
        return self.search_results