import datetime
import re
import zipfile
from decimal import Decimal

import pytest
from openpyxl import Workbook

from donormail.sources import (
    SourceError,
    parse_date,
    parse_money,
    read_table,
    text,
)

COLUMNS = {"date": "Date", "name": "Donor", "amount": "Amount"}

# report title rows, a blank first column, and a total row
QBO_CSV = """\
Anytown Charity,,,
Sales by Donor Detail,,,

,Date,Donor,Amount
,01/15/2025,Jane Doe,100.00
,02/01/2025,Fund:John Doe,"1,250.00  "

TOTAL,,,"$ 1,350.00  "
"""


def test_read_csv_skips_title_rows(tmp_path):
    """Header row is found below report titles and blank rows are dropped."""

    path = tmp_path / "gifts.csv"
    path.write_text(QBO_CSV)

    records = read_table(path, COLUMNS)
    assert [r["name"] for r in records] == ["Jane Doe", "Fund:John Doe", ""]
    assert records[0]["line"] == 5
    assert records[-1]["amount"] == "$ 1,350.00  "


def test_read_excel(tmp_path):
    """Excel rows keep native dates and numbers."""

    workbook = Workbook()
    sheet = workbook.worksheets[0]
    sheet.append(["Report title"])
    sheet.append(["Date", "Donor", "Amount", "Extra"])
    sheet.append([datetime.datetime(2025, 3, 1), "Jane Doe", 25.5, "x"])
    path = tmp_path / "gifts.xlsx"
    workbook.save(path)

    records = read_table(path, COLUMNS)
    assert len(records) == 1
    assert records[0]["date"] == datetime.datetime(2025, 3, 1)
    assert records[0]["amount"] == 25.5
    assert "Extra" not in records[0]


def test_read_excel_wrong_size(tmp_path):
    """Workbooks that store a wrong sheet size are read in full."""

    built = tmp_path / "built.xlsx"
    book = Workbook()
    sheet = book.active
    assert sheet is not None
    sheet.append(["Date", "Donor", "Amount"])
    sheet.append(["01/15/2025", "Jane Doe", 100])
    book.save(built)

    # rewrite the stored size as a single cell
    path = tmp_path / "gifts.xlsx"
    with zipfile.ZipFile(built) as source, zipfile.ZipFile(path, "w") as target:
        for item in source.infolist():
            data = source.read(item.filename)
            if item.filename == "xl/worksheets/sheet1.xml":
                data = re.sub(rb'<dimension ref="[^"]*"', b'<dimension ref="A1"', data)
            target.writestr(item, data)

    (record,) = read_table(path, COLUMNS)
    assert record["amount"] == 100


def test_read_missing_header(tmp_path):
    """Missing columns are reported by name."""

    path = tmp_path / "gifts.csv"
    path.write_text("Date,Donor\n1/1/2025,Jane\n")
    with pytest.raises(SourceError, match="No header row with columns Amount"):
        read_table(path, COLUMNS)


def test_read_missing_file(tmp_path):
    """Missing files are reported by path."""

    with pytest.raises(SourceError, match="File not found"):
        read_table(tmp_path / "nope.csv", COLUMNS)


def test_read_windows_csv(tmp_path):
    """CSV files saved in the Windows encoding are read."""

    path = tmp_path / "gifts.csv"
    path.write_bytes("Date,Donor,Amount\n01/15/2025,José Ruiz,10\n".encode("cp1252"))
    (record,) = read_table(path, COLUMNS)
    assert record["name"] == "José Ruiz"


def test_read_old_excel(tmp_path):
    """Old .xls files are reported with what to do."""

    path = tmp_path / "gifts.xls"
    path.write_bytes(b"not a workbook")
    with pytest.raises(SourceError, match="Save this file as .xlsx or CSV"):
        read_table(path, COLUMNS)


def test_read_damaged_excel(tmp_path):
    """A damaged workbook is reported instead of crashing."""

    path = tmp_path / "gifts.xlsx"
    path.write_bytes(b"not a workbook")
    with pytest.raises(SourceError, match="Not a readable Excel file"):
        read_table(path, COLUMNS)


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        ("100", "100.00"),
        ("1,250.00  ", "1250.00"),
        ("$ 1,350.00", "1350.00"),
        ("(25.00)", "-25.00"),
        ("-25", "-25.00"),
        (25.5, "25.50"),
        (100, "100.00"),
        (0.1 + 0.2, "0.30"),
        (89.7425, "89.74"),
        (0.125, "0.13"),
        ("2.675", "2.68"),
        ("(0.125)", "-0.13"),
    ],
)
def test_parse_money(value, expected):
    """Money parses from text and numbers into cents."""

    assert parse_money(value) == Decimal(expected)


@pytest.mark.parametrize("value", ["", None, "abc", "12.3.4"])
def test_parse_money_invalid(value):
    """Invalid amounts raise ValueError."""

    with pytest.raises(ValueError, match="amount"):
        parse_money(value)


def test_parse_date():
    """Dates parse from text, dates, and datetimes."""

    expected = datetime.date(2025, 1, 5)
    assert parse_date("1/5/2025", "%m/%d/%Y") == expected
    assert parse_date("01/05/2025", "%m/%d/%Y") == expected
    assert parse_date(expected, "%m/%d/%Y") == expected
    assert parse_date(datetime.datetime(2025, 1, 5, 9), "%m/%d/%Y") == expected


@pytest.mark.parametrize("value", ["", "2025-01-05", "13/1/2025"])
def test_parse_date_invalid(value):
    """Invalid dates raise ValueError."""

    with pytest.raises(ValueError, match="date"):
        parse_date(value, "%m/%d/%Y")


def test_text():
    """Cells convert to stripped text."""

    assert text(None) == ""
    assert text("  a b ") == "a b"
    assert text(2134.0) == "2134"
    assert text(2.5) == "2.5"
