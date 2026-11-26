import csv
import datetime
import warnings
from decimal import ROUND_HALF_UP, Decimal, InvalidOperation
from pathlib import Path
from zipfile import BadZipFile

from openpyxl import load_workbook
from openpyxl.utils.exceptions import InvalidFileException

CENTS = Decimal("0.01")
EXCEL_SUFFIXES = {".xlsx", ".xlsm"}

# CSV files from Excel or QuickBooks Desktop on Windows are often not UTF-8
CSV_ENCODINGS = ("utf-8-sig", "cp1252")


class SourceError(Exception):
    """Unreadable input file."""


def read_table(path, columns):
    """Read records keyed by field name from a CSV or Excel file.

    The header is the first row containing every mapped column name, so
    title rows above it are skipped. Blank rows are dropped. Each record
    includes its line number for error messages.
    """

    path = Path(path)
    if not path.is_file():
        raise SourceError(f"File not found: {path}")
    if path.suffix.lower() == ".xls":
        raise SourceError(f"{path}: Save this file as .xlsx or CSV to read it")
    rows = (
        _read_excel(path) if path.suffix.lower() in EXCEL_SUFFIXES else _read_csv(path)
    )

    # map field names to column positions
    start, header = _find_header(path, rows, set(columns.values()))
    positions = {field: header.index(name) for field, name in columns.items()}

    records = []
    for line, row in enumerate(rows[start + 1 :], start=start + 2):
        if not any(text(cell) for cell in row):
            continue
        record = {
            field: row[index] if index < len(row) else None
            for field, index in positions.items()
        }
        record["line"] = line
        records.append(record)

    return records


def _read_csv(path):
    """Read all rows from a CSV file."""

    for encoding in CSV_ENCODINGS:
        try:
            with path.open(newline="", encoding=encoding) as f:
                return list(csv.reader(f))
        except UnicodeDecodeError:
            continue
    raise SourceError(f"{path}: Not a readable text file, save it as UTF-8 CSV")


def _read_excel(path):
    """Read all rows from the first sheet of an Excel file."""

    # QuickBooks workbooks have no default style, which openpyxl warns about
    with warnings.catch_warnings():
        warnings.filterwarnings("ignore", "Workbook contains no default style")
        try:
            workbook = load_workbook(path, read_only=True, data_only=True)
        except (InvalidFileException, BadZipFile, KeyError) as e:
            raise SourceError(f"{path}: Not a readable Excel file ({e})") from e
    try:
        sheet = workbook.worksheets[0]

        # read every cell, since some programs store a wrong sheet size
        sheet.reset_dimensions()
        return [list(row) for row in sheet.iter_rows(values_only=True)]
    finally:
        workbook.close()


def _find_header(path, rows, names):
    """Find the header row index and its cleaned cells."""

    for index, row in enumerate(rows):
        header = [text(cell) for cell in row]
        if names <= set(header):
            return index, header
    raise SourceError(f"{path}: No header row with columns {', '.join(sorted(names))}")


def text(value):
    """Convert a cell to stripped text."""

    if value is None:
        return ""
    # whole numbers from Excel, e.g. zip codes, lose the trailing .0
    if isinstance(value, float) and value.is_integer():
        return str(int(value))
    return str(value).strip()


def parse_money(value):
    """Parse a cell into a Decimal amount.

    Accepts numbers and text such as "1,234.50", "$ 25.00", or "(25.00)".
    """

    if isinstance(value, (int, float, Decimal)) and not isinstance(value, bool):
        return Decimal(str(value)).quantize(CENTS, rounding=ROUND_HALF_UP)

    raw = text(value)
    if not raw:
        raise ValueError("Missing amount")

    # parentheses mark a negative amount
    cleaned = raw.replace("$", "").replace(",", "").replace(" ", "")
    negative = cleaned.startswith("(") and cleaned.endswith(")")
    cleaned = cleaned.strip("()")

    try:
        amount = Decimal(cleaned)
    except InvalidOperation:
        raise ValueError(f"Invalid amount {raw!r}") from None
    return (-amount if negative else amount).quantize(CENTS, rounding=ROUND_HALF_UP)


def parse_date(value, date_format):
    """Parse a cell into a date."""

    if isinstance(value, datetime.datetime):
        return value.date()
    if isinstance(value, datetime.date):
        return value

    raw = text(value)
    if not raw:
        raise ValueError("Missing date")
    try:
        return datetime.datetime.strptime(raw, date_format).date()
    except ValueError:
        raise ValueError(f"Invalid date {raw!r}") from None
