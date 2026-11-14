"""IOA activity logs view — display sending history, failures, and system events."""

from __future__ import annotations

from PySide6.QtCore import QTimer
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QTableWidget, QTableWidgetItem,
    QPushButton, QHBoxLayout, QLabel, QHeaderView,
)

from data.database import Database


class LogsView(QWidget):
    def __init__(self, database: Database, parent=None):
        super().__init__(parent)
        self.db = database
        self._build_ui()
        QTimer.singleShot(100, self.refresh)

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)

        toolbar = QHBoxLayout()
        btn_refresh = QPushButton("تحديث")
        btn_refresh.clicked.connect(self.refresh)
        toolbar.addWidget(btn_refresh)
        toolbar.addStretch()
        layout.addLayout(toolbar)

        self.table = QTableWidget(0, 6)
        self.table.setHorizontalHeaderLabels([
            "التاريخ", "المستوى", "المصدر", "الرسالة", "المعهد", "الحملة",
        ])
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.table.setAlternatingRowColors(True)
        self.table.setEditTriggers(QTableWidget.NoEditTriggers)
        layout.addWidget(self.table)

    def refresh(self) -> None:
        logs = self.db.list_error_logs(limit=200)
        self.table.setRowCount(len(logs))
        for row, log in enumerate(logs):
            self.table.setItem(row, 0, QTableWidgetItem(log.timestamp))
            self.table.setItem(row, 1, QTableWidgetItem(log.level))
            self.table.setItem(row, 2, QTableWidgetItem(log.source))
            self.table.setItem(row, 3, QTableWidgetItem(log.message))
            self.table.setItem(row, 4, QTableWidgetItem(log.contact_id or "-"))
            self.table.setItem(row, 5, QTableWidgetItem(log.campaign_id or "-"))
