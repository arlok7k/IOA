"""IOA campaigns view — create, start, pause, resume, review campaigns."""

from __future__ import annotations

from PySide6.QtCore import Qt, QTimer
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QTableWidget, QTableWidgetItem,
    QPushButton, QLabel, QLineEdit, QMessageBox, QHeaderView, QInputDialog,
)

from data.database import Database
from data.models import CampaignState
from core.campaign_manager import CampaignManager


class CampaignView(QWidget):
    def __init__(self, database: Database, campaign_manager: CampaignManager,
                 parent=None):
        super().__init__(parent)
        self.db = database
        self.cm = campaign_manager
        self._build_ui()
        QTimer.singleShot(100, self.refresh)

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)

        toolbar = QHBoxLayout()
        self.btn_new = QPushButton("جديدة حملة")
        self.btn_new.clicked.connect(self._new_campaign)
        self.btn_start = QPushButton("بدء الحملة المختارة")
        self.btn_start.clicked.connect(self._start_selected)
        self.btn_pause = QPushButton("إيقاف الحملة المختارة")
        self.btn_pause.clicked.connect(self._pause_selected)
        self.btn_resume = QPushButton("استئناف الحملة المختارة")
        self.btn_resume.clicked.connect(self._resume_selected)
        btn_refresh = QPushButton("تحديث")
        btn_refresh.clicked.connect(self.refresh)
        for btn in (self.btn_new, self.btn_start, self.btn_pause,
                    self.btn_resume, btn_refresh):
            toolbar.addWidget(btn)
        toolbar.addStretch()
        layout.addLayout(toolbar)

        self.table = QTableWidget(0, 7)
        self.table.setHorizontalHeaderLabels([
            "اسم الحملة", "الحالة", "الإجمالي", "مرسلة", "فشلت", "غير مؤكدة", "تاريخ الإنشاء",
        ])
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.table.setAlternatingRowColors(True)
        self.table.setSelectionBehavior(QTableWidget.SelectRows)
        self.table.setEditTriggers(QTableWidget.NoEditTriggers)
        layout.addWidget(self.table)

        self.lbl_info = QLabel("")
        layout.addWidget(self.lbl_info)

    def refresh(self) -> None:
        campaigns = self.db.list_campaigns()
        self.table.setRowCount(len(campaigns))
        for row, camp in enumerate(campaigns):
            self.table.setItem(row, 0, QTableWidgetItem(camp.name))
            self.table.setItem(row, 1, QTableWidgetItem(camp.state))
            self.table.setItem(row, 2, QTableWidgetItem(str(camp.total_contacts)))
            self.table.setItem(row, 3, QTableWidgetItem(str(camp.sent_count)))
            self.table.setItem(row, 4, QTableWidgetItem(str(camp.failed_count)))
            self.table.setItem(row, 5, QTableWidgetItem(str(camp.uncertain_count)))
            self.table.setItem(row, 6, QTableWidgetItem(camp.created_at or ""))
            # store campaign id in first item
            self.table.item(row, 0).setData(Qt.UserRole, camp.id)

    def _selected_campaign_id(self):
        row = self.table.currentRow()
        if row < 0:
            return None
        return self.table.item(row, 0).data(Qt.UserRole)

    def _selected_campaign(self):
        cid = self._selected_campaign_id()
        if cid is None:
            return None
        return self.db.get_campaign(cid)

    def _new_campaign(self) -> None:
        name, ok = QInputDialog.getText(self, "حملة جديدة", "اسم الحملة:")
        if ok and name.strip():
            self.cm.create_campaign(name.strip())
            self.refresh()

    def _start_selected(self) -> None:
        camp = self._selected_campaign()
        if not camp:
            QMessageBox.information(self, "تنبيه", "اختر حملة أولًا.")
            return
        if self.cm.start_campaign(camp.id):
            self.refresh()
        else:
            QMessageBox.warning(self, "خطأ", "تعذر بدء الحملة.")

    def _pause_selected(self) -> None:
        camp = self._selected_campaign()
        if not camp:
            QMessageBox.information(self, "تنبيه", "اختر حملة أولًا.")
            return
        self.cm.pause_campaign(camp.id)
        self.refresh()

    def _resume_selected(self) -> None:
        camp = self._selected_campaign()
        if not camp:
            QMessageBox.information(self, "تنبيه", "اختر حملة أولًا.")
            return
        self.cm.resume_campaign(camp.id)
        self.refresh()
