from PyQt5.QtCore import Qt, pyqtSignal
from PyQt5.QtWidgets import QTreeWidget, QTreeWidgetItem

class TOCWidget(QTreeWidget):
    """Custom Tree Widget for displaying the PDF Table of Contents."""
    # Signal now emits both page number and y-position
    toc_link_clicked = pyqtSignal(int, float)

    def __init__(self, parent=None):
        super().__init__(parent)
        # self.setHeaderLabels(["Table of Contents"])
        self.setHeaderHidden(True)  # Hide the header row
        self.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.setFixedWidth(250)
        self.itemClicked.connect(self._item_clicked)
        self.setToolTip("Click an item to jump to that page.")

    def _item_clicked(self, item, col):
        """Handle click on a TOC item."""
        page_num = item.data(0, Qt.UserRole)
        y_pos = item.data(0, Qt.UserRole + 1)
        if page_num is not None:
            self.toc_link_clicked.emit(page_num, y_pos if y_pos is not None else 0.0)

    def load_toc(self, toc_data):
        """Clears existing items and loads new TOC data from detailed format."""
        self.clear()
        root = self.invisibleRootItem()
        item_stack = {-1: root}

        for entry in toc_data:
            # Handle both simple and detailed TOC formats
            if len(entry) == 3:
                # Simple format: [level, title, page_num]
                level, title, page_num = entry
                y_pos = 0.0
            elif len(entry) == 4:
                # Detailed format: [level, title, page_num, details_dict]
                level, title, page_num, details = entry
                # Extract the y-coordinate from the 'to' Point
                to_point = details.get('to')
                y_pos = to_point.y if to_point else 0.0
            else:
                continue

            parent = item_stack.get(level - 1, root)
            new_item = QTreeWidgetItem(parent, [title])
            new_item.setData(0, Qt.UserRole, int(page_num))
            new_item.setData(0, Qt.UserRole + 1, float(y_pos))
            item_stack[level] = new_item

            # Clean up deeper levels
            item_stack = {k: v for k, v in item_stack.items() if k <= level}

        self.expandAll()