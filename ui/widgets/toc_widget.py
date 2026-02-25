from PyQt5.QtCore import Qt, pyqtSignal
from PyQt5.QtWidgets import QTreeWidget, QTreeWidgetItem


class TOCWidget(QTreeWidget):
    """Custom Tree Widget for displaying the PDF Table of Contents."""

    toc_link_clicked = pyqtSignal(int, float)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setHeaderHidden(True)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.setFixedWidth(250)
        self.itemClicked.connect(self._item_clicked)
        self.setToolTip("Click an item to jump to that page.")

    def _item_clicked(self, item, col):
        page_num = item.data(0, Qt.UserRole)
        y_pos = item.data(0, Qt.UserRole + 1)
        if page_num is not None:
            self.toc_link_clicked.emit(page_num, y_pos if y_pos is not None else 0.0)

    def load_toc(self, toc_data):
        self.clear()
        root = self.invisibleRootItem()
        item_stack = {-1: root}

        for entry in toc_data:
            if len(entry) == 4:
                level, title, page_num, y_pos = entry
            elif len(entry) == 3:
                level, title, page_num = entry
                y_pos = 0.0
            else:
                continue

            if not title or not title.strip():
                title = f"Section {page_num}"

            parent = item_stack.get(level - 1, root)
            new_item = QTreeWidgetItem(parent, [title])
            new_item.setData(0, Qt.UserRole, int(page_num))
            new_item.setData(0, Qt.UserRole + 1, float(y_pos))
            new_item.setToolTip(0, f"{title} - Page {page_num}")
            item_stack[level] = new_item
            item_stack = {k: v for k, v in item_stack.items() if k <= level}

        self.expandAll()

    def clear_toc(self):
        self.clear()
        self.invisibleRootItem().takeChildren()
