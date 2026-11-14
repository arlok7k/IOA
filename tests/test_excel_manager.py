"""Tests for the Excel manager (IOA phase 2)."""

import os
import tempfile
from pathlib import Path

import pytest
from openpyxl import Workbook

from data.excel_manager import ExcelManager, HEADER_ALIASES


@pytest.fixture
def xlsx_path(tmp_path):
    p = tmp_path / "contacts.xlsx"
    wb = Workbook()
    ws = wb.active
    ws.title = "Sheet1"
    ws.append(
        ["اسم المعهد", "رقم الهاتف", "العنوان", "حالة التواصل", "ملاحظات"]
    )
    ws.append(["معهد المستقبل", "771234567", "صنعاء", "قيد الانتظار", ""])
    ws.append(["معهد التكنولوجيا", "+967711234567", "عدن", "تم التواصل", ""])
    wb.save(str(p))
    return str(p)


def test_discover_files_empty(tmp_path):
    mgr = ExcelManager(str(tmp_path / "nonexistent"))
    assert mgr.discover_files() == []


def test_discover_files_finds_excel_and_txt(tmp_path):
    (tmp_path / "a.xlsx").write_bytes(b"")
    (tmp_path / "b.txt").write_text("مرحبا", encoding="utf-8")
    (tmp_path / "c.csv").write_text("x", encoding="utf-8")
    mgr = ExcelManager(str(tmp_path))
    files = mgr.discover_files()
    kinds = {f.kind for f in files}
    assert "excel" in kinds
    assert "txt" in kinds
    names = {f.name for f in files}
    assert "a.xlsx" in names
    assert "b.txt" in names
    assert "c.csv" not in names


def test_suggest_mapping_arabic_headers(xlsx_path):
    mgr = ExcelManager("")
    headers = ["اسم المعهد", "رقم الهاتف", "العنوان", "حالة التواصل", "ملاحظات"]
    mapping = mgr.suggest_mapping(headers)
    assert mapping.field_to_column_index.get("institute_name") == 1
    assert mapping.field_to_column_index.get("phone_number") == 2
    assert mapping.has_required() is True


def test_normalize_header():
    from data.excel_manager import ExcelManager as EM
    assert EM.normalize_header("  اسم المعهد  ") == "اسم المعهد"


def test_read_contacts(xlsx_path):
    mgr = ExcelManager("")
    headers = ["اسم المعهد", "رقم الهاتف", "العنوان", "حالة التواصل", "ملاحظات"]
    mapping = mgr.suggest_mapping(headers)
    contacts = mgr.read_contacts(Path(xlsx_path), "Sheet1", mapping)
    assert len(contacts) == 2
    assert contacts[0].institute_name == "معهد المستقبل"
    assert contacts[0].phone_original == "771234567"
    assert contacts[1].institute_name == "معهد التكنولوجيا"
    # Arabic status interpretation
    assert contacts[1].contact_status in ("sent", "تم التواصل")


def test_header_aliases_known():
    assert HEADER_ALIASES["اسم المعهد"] == "institute_name"
    assert HEADER_ALIASES["رقم الهاتف"] == "phone_number"
    assert HEADER_ALIASES["العنوان"] == "address"
    assert HEADER_ALIASES["حالة التواصل"] == "contact_status"
    assert HEADER_ALIASES["ملاحظات"] == "notes"
