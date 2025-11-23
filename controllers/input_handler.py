from PyQt5.QtCore import Qt, QRect
from PyQt5.QtGui import QKeySequence

class UserInputHandler:
    """
    Handles all keyboard and mouse inputs for the PDF reader application.
    """
    def __init__(self, main_window):
        """
        Initializes the handler with a reference to the main window.
        
        Args:
            main_window (PDFReader): A reference to the main application window.
        """
        self.main_window = main_window

    def handle_key_press(self, event):
        """
        Handles key press events for the main window.
        """
        if event.matches(QKeySequence.Copy):
            self.main_window.copy_selected_text()
            event.accept()
        elif event.matches(QKeySequence.Find):
            self.main_window.show_search_bar()
            event.accept()
        elif event.matches(QKeySequence.Open):
            self.main_window.open_pdf()
            event.accept()
        elif event.matches(QKeySequence.Close):
            self.main_window.close_pdf()
            event.accept()
        elif event.matches(QKeySequence.Save):
            self.main_window.save_annotations_to_pdf()
            event.accept()
        elif event.key() == Qt.Key_Escape:
            if self.main_window.search_frame.isVisible():
                self.main_window._hide_search_bar()
                event.accept()
        else:
            event.ignore()

    def handle_page_label_mouse_press(self, label, event):
        """
        Handles mouse press events for a page label.
        
        Args:
            label (ClickablePageLabel): The page label widget.
            event (QMouseEvent): The mouse event.
        """
        if event.button() == Qt.LeftButton:
            word_at_pos = self._get_word_at_pos(label, event.pos())
            
            if not word_at_pos and not (event.modifiers() & Qt.ControlModifier):
                label.selected_words.clear()
                label.selection_rects = []
                label.start_pos = None
                label.end_pos = None
                label.update()
                return

            label.start_pos = event.pos()
            label.end_pos = None
            label._selection_at_start = label.selected_words.copy()
            label.update()

    def handle_page_label_mouse_move(self, label, event):
        """
        Handles mouse move events for a page label.
        
        Args:
            label (ClickablePageLabel): The page label widget.
            event (QMouseEvent): The mouse event.
        """
        if event.buttons() & Qt.LeftButton and label.word_data and label.start_pos:
            label.end_pos = event.pos()
            self._update_selection(label, event.modifiers())
            label.update()
        
    def handle_page_label_mouse_release(self, label, event):
        """
        Handles mouse release events for a page label.
        
        Args:
            label (ClickablePageLabel): The page label widget.
            event (QMouseEvent): The mouse event.
        """
        if event.button() == Qt.LeftButton and label.word_data and label.start_pos:
            label.end_pos = event.pos()
            self._update_selection(label, event.modifiers())
            label.update()

    def _get_word_at_pos(self, label, pos):
        """
        Finds the word at the given position.
        
        Args:
            label (ClickablePageLabel): The page label widget.
            pos (QPoint): The position to check.
            
        Returns:
            list or None: The word data list if a word is found, otherwise None.
        """
        if not label.word_data or not pos:
            return None
        
        for word_info in label.word_data:
            bbox = word_info[:4]
            word_rect = QRect(
                int(bbox[0] * label.zoom_level),
                int(bbox[1] * label.zoom_level),
                int((bbox[2] - bbox[0]) * label.zoom_level),
                int((bbox[3] - bbox[1]) * label.zoom_level)
            )
            
            if word_rect.contains(pos):
                return word_info
        return None

    def _update_selection(self, label, modifiers):
        """
        Updates the selected words based on a drag event.
        
        Args:
            label (ClickablePageLabel): The page label widget.
            modifiers (Qt.KeyboardModifiers): The keyboard modifiers.
        """
        if not label.start_pos or not label.end_pos or not label.word_data:
            return

        all_words_in_order = sorted(label.word_data, key=lambda x: (x[5], x[6], x[7]))

        start_word = self._get_word_at_pos(label, label.start_pos)
        end_word = self._get_word_at_pos(label, label.end_pos)

        if not start_word or not end_word:
            label.selection_rects = self._get_merged_selection_rects(label)
            return
        
        try:
            start_index = all_words_in_order.index(start_word)
            end_index = all_words_in_order.index(end_word)
        except ValueError:
            return # Word not found in sorted list, should not happen

        min_index = min(start_index, end_index)
        max_index = max(start_index, end_index)

        words_in_drag = set(all_words_in_order[min_index:max_index + 1])
        
        if modifiers & Qt.ControlModifier:
            label.selected_words = label._selection_at_start.symmetric_difference(words_in_drag)
        else:
            is_starting_from_selected = start_word in label._selection_at_start
            
            if is_starting_from_selected:
                label.selected_words = label._selection_at_start.difference(words_in_drag)
            else:
                label.selected_words = words_in_drag

        label.selection_rects = self._get_merged_selection_rects(label)

    def _get_merged_selection_rects(self, label):
        """
        Generates non-overlapping selection rectangles for each line containing
        selected words.
        
        Args:
            label (ClickablePageLabel): The page label widget.
            
        Returns:
            list: A list of QRect objects for the selection highlights.
        """
        if not label.selected_words:
            return []
        
        lines_to_highlight = {}
        for word_info in label.selected_words:
            key = (word_info[5], word_info[6])
            if key not in lines_to_highlight:
                lines_to_highlight[key] = []
            lines_to_highlight[key].append(word_info)
            
        selection_rects = []
        for line_key, words_in_line in lines_to_highlight.items():
            if not words_in_line:
                continue
            
            words_in_line.sort(key=lambda x: x[0])
            
            min_x = min(word[0] for word in words_in_line)
            max_x = max(word[2] for word in words_in_line)
            
            first_word_y0 = words_in_line[0][1]
            first_word_y1 = words_in_line[0][3]
            line_height = first_word_y1 - first_word_y0
            
            line_rect = QRect(
                int(min_x * label.zoom_level),
                int(first_word_y0 * label.zoom_level),
                int((max_x - min_x) * label.zoom_level),
                int(line_height * label.zoom_level)
            )
            selection_rects.append(line_rect)
        
        return selection_rects
