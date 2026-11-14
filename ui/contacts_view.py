"""IOA contacts view — display, search, filter, and inspect institutes."""

from __future__ import annotations

from PySide6.QtCore import Qt, QTimer
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QTableWidget, QTableWidgetItem,
    QLineEdit, QPushButton, QLabel, QComboBox, QMessageBox, QHeaderView,
)

from data.database import Database
from data.models import ContactStatus


class ContactsView(QWidget):
    def __init__(self, database: Database, campaign_manager, parent=None):
        super().__init__(parent)
        self.db = database
        self.campaign_manager = campaign_manager
        self._contacts = []
        self._build_ui()
        # Auto-refresh shortly after show
        QTimer.singleShot(100, self.refresh)

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)

        # Toolbar
        toolbar = QHBoxLayout()
        self.search = QLineEdit()
        self.search.setPlaceholderText("ابحث باسم المعهد أو رقم الهاتف…")
        self.search.textChanged.connect(self._filter)
        self.status_filter = QComboBox()
        self.status_filter.addItem("جميع الحالات", None)
        for status in ContactStatus.ALL:
            self.status_filter.addItem(status, status)
        self.status_filter.currentIndexChanged.connect(self._filter)
        btn_refresh = QPushButton("تحديث")
        btn_refresh.clicked.connect(self.refresh)
        toolbar.addWidget(QLabel("بحث:"))
        toolbar.addWidget(self.search)
        toolbar.addWidget(QLabel("الحالة:"))
        toolbar.addWidget(self.status_filter)
        toolbar.addWidget(btn_refresh)
        toolbar.addStretch()
        layout.addLayout(toolbar)

        # Table
        self.table = QTableWidget(0, 7)
        self.table.setHorizontalHeaderLabels([
            "اسم المعهد", "رقم الهاتف", "العنوان", "الحالة", "الملاحظات", "آخر إرسال", "الحملة",
        ])
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.table.setAlternatingRowColors(True)
        self.table.setSelectionBehavior(QTableWidget.SelectRows)
        self.table.setEditTriggers(QTableWidget.NoEditTriggers)
        layout.addWidget(self.table)

        self.lbl_count = QLabel("0 مؤسسة")
        layout.addWidget(self.lbl_count)

    def refresh(self) -> None:
        campaign_id = getattr(self.campaign_manager, "active_campaign_id", None)
        self._contacts = self.db.list_contacts(campaign_id=campaign_id)
        self._populate(self._contacts)

    def _populate(self, contacts) -> None:
        self.table.setRowCount(len(contacts))
        for row, contact in enumerate(contacts):
            self.table.setItem(row, 0, QTableWidgetItem(contact.institute_name))
            self.table.setItem(row, 1, QTableWidgetItem(contact.phone_original))
            self.table.setItem(row, 2, QTableWidgetItem(contact.address))
            self.table.setItem(row, 3, QTableWidgetItem(contact.contact_status))
            self.table.setItem(row, 4, QTableWidgetItem(contact.notes))
            self.table.setItem(row, 5, QTableWidgetItem(contact.last_sent_at or "-"))
            self.table.setItem(row, 6, QTableWidgetItem(contact.campaign_id or "-"))
        self.lbl_count.setText(f"{len(contacts)} مؤسسة")

    def _filter(self) -> None:
        text = self.search.text().lower()
        status = self.status_filter.currentData()
        filtered = []
        for c in self._contacts:
            if text and text not in c.institute_name.lower() and text not in c.phone_original:
                continue
            if status is not None and c.contact_status != status:
                continue
            filtered.append(c)
        self._populate(filtered)
