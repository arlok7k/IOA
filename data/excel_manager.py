"""IOA Excel manager.

Discovers Excel workbooks and TXT templates in the input directory,
reads institute data with flexible column mapping (Arabic / English),
and safely updates the workbook while preserving all original columns,
rows, formatting, and unrelated information.
"""

from __future__ import annotations

import shutil
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Optional

from openpyxl import load_workbook, Workbook
from openpyxl.worksheet.worksheet import Worksheet

from data.models import Contact, ContactStatus


# ---------------------------------------------------------------------------
# Known header aliases (Arabic / English) -> canonical field
# ---------------------------------------------------------------------------
HEADER_ALIASES: dict[str, str] = {
    # Institute name
    "institute name": "institute_name",
    "اسم المعهد": "institute_name",
    "اسم المؤسسة": "institute_name",
    "المعهد": "institute_name",
    "ال istituzione": "institute_name",
    # Phone number
    "phone number": "phone_number",
    "رقم الهاتف": "phone_number",
    "رقم الجوال": "phone_number",
    "الجوال": "phone_number",
    "الهاتف": "phone_number",
    "whatsapp": "phone_number",
    "واتساب": "phone_number",
    # Address
    "address": "address",
    "العنوان": "address",
    "الموقع": "address",
    "site": "address",
    # Contact status
    "contact status": "contact_status",
    "حالة التواصل": "contact_status",
    "حالة الاتصال": "contact_status",
    "الحالة": "contact_status",
    # Notes
    "notes": "notes",
    "ملاحظات": "notes",
    "ملاحظة": "notes",
}


# Canonical field -> list of preferred Arabic/English display labels
CANONICAL_LABELS: dict[str, list[str]] = {
    "institute_name": ["اسم المعهد", "Institute Name"],
    "phone_number": ["رقم الهاتف", "Phone Number"],
    "address": ["العنوان", "Address"],
    "contact_status": ["حالة التواصل", "Contact Status"],
    "notes": ["ملاحظات", "Notes"],
}

REQUIRED_FIELDS = ("institute_name", "phone_number")


@dataclass
class DiscoveredFile:
    path: Path
    kind: str  # "excel" or "txt"
    name: str


@dataclass
class ColumnMapping:
    """User-configured mapping from Excel column index -> canonical field."""
    column_index_to_field: dict[int, str] = field(default_factory=dict)
    field_to_column_index: dict[str, int] = field(default_factory=dict)
    sheet_name: str = ""

    def field_column(self, field: str) -> Optional[int]:
        return self.field_to_column_index.get(field)

    def has_required(self) -> bool:
        return all(
            f in self.field_to_column_index for f in REQUIRED_FIELDS
        )


@dataclass
class ExcelWorkbookInfo:
    path: Path
    sheet_names: list[str]
    active_sheet: str
    column_mapping: Optional[ColumnMapping] = None


class ExcelManager:
    """Safe read/update of Excel workbooks with flexible column detection."""

    EXCEL_EXTENSIONS = (".xlsx", ".xlsm", ".xls")
    TXT_EXTENSIONS = (".txt",)

    def __init__(self, input_directory: str):
        self.input_directory = Path(input_directory)
        self._backup_created = False

    # ------------------------------------------------------------------ #
    # Discovery
    # ------------------------------------------------------------------ #
    def discover_files(self) -> list[DiscoveredFile]:
        """List Excel and TXT files in the input directory (non-recursive)."""
        if not self.input_directory.exists():
            return []
        discovered: list[DiscoveredFile] = []
        for item in sorted(self.input_directory.iterdir()):
            if not item.is_file():
                continue
            suffix = item.suffix.lower()
            if suffix in self.EXCEL_EXTENSIONS:
                discovered.append(
                    DiscoveredFile(path=item, kind="excel", name=item.name)
                )
            elif suffix in self.TXT_EXTENSIONS:
                discovered.append(
                    DiscoveredFile(path=item, kind="txt", name=item.name)
                )
        return discovered

    def discover_excel_workbooks(self) -> list[DiscoveredFile]:
        return [f for f in self.discover_files() if f.kind == "excel"]

    def discover_txt_templates(self) -> list[DiscoveredFile]:
        return [f for f in self.discover_files() if f.kind == "txt"]

    # ------------------------------------------------------------------ #
    # Workbook inspection
    # ------------------------------------------------------------------ #
    def inspect_workbook(self, path: Path) -> ExcelWorkbookInfo:
        wb = load_workbook(str(path), read_only=True, data_only=True)
        try:
            sheet_names = wb.sheetnames
            active = wb.active.title if wb.active else (sheet_names[0] if sheet_names else "")
        finally:
            wb.close()
        return ExcelWorkbookInfo(
            path=path,
            sheet_names=sheet_names,
            active_sheet=active,
        )

    def read_header_row(self, path: Path, sheet_name: str) -> list[str]:
        """Return the first row as header strings (stripped)."""
        wb = load_workbook(str(path), read_only=True, data_only=True)
        try:
            ws = wb[sheet_name]
            first_row = next(ws.iter_rows(min_row=1, max_row=1, values_only=True))
            return [str(cell).strip() if cell is not None else "" for cell in first_row]
        finally:
            wb.close()

    # ------------------------------------------------------------------ #
    # Column mapping
    # ------------------------------------------------------------------ #
    @staticmethod
    def normalize_header(header: str) -> str:
        return header.strip().lower()

    @staticmethod
    def suggest_mapping(headers: list[str]) -> ColumnMapping:
        """Auto-suggest a column mapping based on header aliases."""
        mapping = ColumnMapping()
        for idx, header in enumerate(headers, start=1):
            if not header:
                continue
            norm = ExcelManager.normalize_header(header)
            field = HEADER_ALIASES.get(norm)
            if field:
                mapping.column_index_to_field[idx] = field
                mapping.field_to_column_index[field] = idx
        return mapping

    # ------------------------------------------------------------------ #
    # Reading contacts
    # ------------------------------------------------------------------ #
    def read_contacts(
        self,
        path: Path,
        sheet_name: str,
        mapping: ColumnMapping,
        campaign_id: Optional[str] = None,
    ) -> list[Contact]:
        """Read institute rows from Excel using the provided column mapping."""
        contacts: list[Contact] = []
        wb = load_workbook(str(path), read_only=True, data_only=True)
        try:
            ws = wb[sheet_name]
            rows = ws.iter_rows(values_only=True)
            header = next(rows, None)  # skip header row
            for row_index, row in enumerate(rows, start=2):  # Excel row numbers
                if not any(cell is not None and str(cell).strip() for cell in row):
                    continue  # skip fully empty rows
                contact = self._row_to_contact(
                    row, mapping, excel_row_index=row_index, campaign_id=campaign_id
                )
                if contact.institute_name or contact.phone_original:
                    contacts.append(contact)
        finally:
            wb.close()
        return contacts

    def _row_to_contact(
        self,
        row: tuple,
        mapping: ColumnMapping,
        excel_row_index: int,
        campaign_id: Optional[str],
    ) -> Contact:
        values: dict[str, str] = {}
        for col_idx, field in mapping.column_index_to_field.items():
            if col_idx <= len(row):
                cell = row[col_idx - 1]
                values[field] = str(cell).strip() if cell is not None else ""

        institute_name = values.get("institute_name", "")
        phone_original = values.get("phone_number", "")
        address = values.get("address", "")
        contact_status = values.get("contact_status", ContactStatus.PENDING)
        notes = values.get("notes", "")

        # Interpret existing Arabic status values
        if contact_status in ("تم التواصل", "مقبول", "تم الإرسال", "مرسل"):
            contact_status = ContactStatus.SENT
        elif contact_status in ("في انتظار الموافقة", "تحت المراجعة"):
            contact_status = ContactStatus.AWAITING_APPROVAL
        elif contact_status in ("مجدول", "مؤجل"):
            contact_status = ContactStatus.SCHEDULED
        elif contact_status in ("فشل", "فاشل"):
            contact_status = ContactStatus.FAILED
        elif contact_status in ("غير مؤكد", "غير واضح"):
            contact_status = ContactStatus.UNCERTAIN
        elif contact_status in ("رقم غير صحيح", "غير صحيح"):
            contact_status = ContactStatus.INVALID_NUMBER
        elif contact_status in ("تم التجاوز", "متخطى"):
            contact_status = ContactStatus.SKIPPED
        elif contact_status in ("قيد الإرسال", "جارٍ الإرسال"):
            contact_status = ContactStatus.SENDING
        elif contact_status == "قيد الانتظار":
            contact_status = ContactStatus.PENDING

        is_contacted = contact_status in (
            ContactStatus.SENT,
            ContactStatus.ARABIC_CONTACTED,
        )

        return Contact(
            excel_row_index=excel_row_index,
            institute_name=institute_name,
            phone_original=phone_original,
            phone_normalized="",  # normalized later by phone validator
            address=address,
            contact_status=contact_status,
            notes=notes,
            is_contacted=is_contacted,
            campaign_id=campaign_id,
        )

    # ------------------------------------------------------------------ #
    # Safe workbook update (preserve everything)
    # ------------------------------------------------------------------ #
    def ensure_backup(self, path: Path) -> Optional[Path]:
        """Create a timestamped backup before the first modification."""
        if self._backup_created:
            return None
        self.input_directory.mkdir(parents=True, exist_ok=True)
        backup_dir = self.input_directory / ".." / "IOA_backups"
        backup_dir.mkdir(parents=True, exist_ok=True)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_name = f"{path.stem}_{timestamp}.bak{path.suffix}"
        backup_path = backup_dir / backup_name
        shutil.copy2(str(path), str(backup_path))
        self._backup_created = True
        return backup_path

    def update_contact_status(
        self,
        path: Path,
        sheet_name: str,
        excel_row_index: int,
        contact_status: str,
        notes_append: Optional[str] = None,
        sent_at: Optional[str] = None,
    ) -> None:
        """Update a single row's status/notes while preserving the workbook."""
        self.ensure_backup(path)

        wb = load_workbook(str(path))
        try:
            ws: Worksheet = wb[sheet_name]

            # Find the status column index dynamically from header row
            status_col = None
            notes_col = None
            sent_col = None
            for col_idx, cell in enumerate(ws[1], start=1):
                if cell.value is None:
                    continue
                norm = str(cell.value).strip().lower()
                if norm in ("حالة التواصل", "case status", "contact status"):
                    status_col = col_idx
                elif norm in ("ملاحظات", "notes"):
                    notes_col = col_idx
                elif norm in ("تاريخ الإرسال", "sent at", "last sent"):
                    sent_col = col_idx

            if status_col is None:
                raise ValueError(
                    "No contact-status column found in the workbook header."
                )

            ws.cell(row=excel_row_index, column=status_col, value=contact_status)

            if notes_append and notes_col:
                current = ws.cell(row=excel_row_index, column=notes_col).value
                current = str(current) if current else ""
                combined = (current + " | " + notes_append).strip(" |")
                ws.cell(row=excel_row_index, column=notes_col, value=combined)

            if sent_at and sent_col:
                ws.cell(row=excel_row_index, column=sent_col, value=sent_at)

            wb.save(str(path))
        finally:
            wb.close()

    def save_workbook(self, wb: Workbook, path: Path) -> None:
        """Generic safe save wrapper."""
        self.ensure_backup(path)
        wb.save(str(path))
