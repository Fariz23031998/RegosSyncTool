import os
import sys
import json
import sqlite3
import time
import uuid
from datetime import datetime
from decimal import Decimal, ROUND_HALF_UP

def application_directory():
    if getattr(sys, "frozen", False):
        return os.path.dirname(os.path.abspath(sys.executable))
    return os.path.dirname(os.path.abspath(__file__))


APP_DIR = application_directory()
CONFIG_PATH = os.path.join(APP_DIR, "config.json")
FIREBIRD_CLIENTS = (
    os.environ.get("FIREBIRD", ""),
    r"C:\Program Files\Firebird\Firebird_3_0",
    r"C:\Program Files (x86)\Firebird\Firebird_3_0",
)

COLUMNS = [
    "LFCode",
    "ItemCode",
    "Department",
    "Name1",
    "Name2",
    "Name3",
    "Label1",
    "Label2",
    "BarcodeType1",
    "BarcodeType2",
    "UnitPrice",
    "VipPrice",
    "WeightUnit",
    "TareWeight",
    "ProducedDateTime",
    "PackageDate",
    "PackageTime",
    "ValidDays",
    "FreshDays",
    "ValidDateCountF",
    "ProducedDateF",
    "PackageDateF",
    "ValidDateF",
    "FreshDateF",
    "DiscountFlag",
    "DiscountUnitPrice",
    "DiscountStartDateTime",
    "DiscountEndDateTime",
    "SpeedCode",
    "ChangePriceFlag",
    "ChangePriceMax",
    "ChangePriceMin",
    "LotNumber",
    "MaxWeight",
    "MinWeight",
    "OncePcs",
    "PLUImportOrder",
    "TaxRate",
    "IceRate",
    "discountRate",
    "UpdateTime",
    "MD5",
]

DEFAULTS = {
    "LFCode": "1",
    "ItemCode": "1",
    "Department": "22",
    "Name1": "",
    "Name2": "",
    "Name3": "",
    "Label1": "1",
    "Label2": "0",
    "BarcodeType1": "7",
    "BarcodeType2": "0",
    "UnitPrice": "0,00",
    "VipPrice": "0",
    "WeightUnit": "0",
    "TareWeight": "0",
    "ProducedDateTime": "01.03.2019 9:45:09",
    "PackageDate": "0",
    "PackageTime": "0",
    "ValidDays": "0",
    "FreshDays": "0",
    "ValidDateCountF": "0",
    "ProducedDateF": "0",
    "PackageDateF": "0",
    "ValidDateF": "0",
    "FreshDateF": "0",
    "DiscountFlag": "0",
    "DiscountUnitPrice": "0",
    "DiscountStartDateTime": "30.12.1899",
    "DiscountEndDateTime": "30.12.1899",
    "SpeedCode": "",
    "ChangePriceFlag": "0",
    "ChangePriceMax": "0",
    "ChangePriceMin": "0",
    "LotNumber": "",
    "MaxWeight": "0",
    "MinWeight": "0",
    "OncePcs": "0",
    "PLUImportOrder": "0",
    "TaxRate": "0",
    "IceRate": "0",
    "discountRate": "0",
    "UpdateTime": "30.12.1899",
    "MD5": "",
}

DEFAULT_CONFIG = {
    "host": "localhost",
    "database": "C:/REGOS BASE/REGOS.FDB",
    "user": "SYSDBA",
    "password": "masterkey",
    "price_type": 1,
    "check_time": 30,
    "plu_file_path": r"C:\REGOS BASE\PLU.txt",
    "units": [
        {
            "name": "weight",
            "regos_unit": 2,
            "weight_unit": 0,
            "barcode_type": 7,
            "label_id": 1,
            "skip_invalid": True,
            "department": 22,
        },
        {
            "name": "piece",
            "regos_unit": 1,
            "weight_unit": 8,
            "barcode_type": 7,
            "label_id": 1,
            "skip_invalid": True,
            "department": 23,
        },
    ],
    "update_sqlite": True,
    "synctool_database": r"C:\Program Files (x86)\SyncTool\Database\Database.db",
}

SQLITE_TEXT = {"ItemCode", "Name1", "Name2", "Name3", "SpeedCode", "LotNumber", "MD5"}
SQLITE_FLOAT = {"UnitPrice", "VipPrice", "DiscountUnitPrice", "ChangePriceMax", "ChangePriceMin", "TaxRate"}
SQLITE_DATE = {"ProducedDateTime", "DiscountStartDateTime", "DiscountEndDateTime"}
SQLITE_DATE_SENTINEL = "1899-12-30 00:00:00"


class ExportError(Exception):
    """The PLU file was not replaced."""


def prepare_firebird_client():
    for folder in FIREBIRD_CLIENTS:
        if folder and os.path.isfile(os.path.join(folder, "fbclient.dll")):
            os.environ["PATH"] = folder + os.pathsep + os.environ.get("PATH", "")
            os.environ.setdefault("FIREBIRD", folder)
            return folder
    return None


prepare_firebird_client()

# fdb 2.0.2 still imports locale.resetlocale, which Python 3.13 removed.
import locale
if not hasattr(locale, "resetlocale"):
    def _resetlocale(category=locale.LC_ALL):
        locale.setlocale(category, "")
    locale.resetlocale = _resetlocale

import fdb
import win32api
import win32event
import winerror


def log(message):
    folder = os.path.join(APP_DIR, "logs")
    os.makedirs(folder, exist_ok=True)
    path = os.path.join(folder, "log-" + datetime.now().strftime("%d-%m-%Y") + ".log")
    line = datetime.now().strftime("%d.%m.%Y %H:%M:%S") + " - " + message
    with open(path, "a", encoding="utf-8") as handle:
        handle.write(line + "\n")
    print(line)


def load_config():
    if os.path.exists(CONFIG_PATH):
        try:
            with open(CONFIG_PATH, "r", encoding="utf-8") as handle:
                return json.load(handle)
        except (OSError, json.JSONDecodeError) as error:
            log(f"Config could not be read ({error}). Defaults were written.")
    with open(CONFIG_PATH, "w", encoding="utf-8") as handle:
        json.dump(DEFAULT_CONFIG, handle, indent=4, ensure_ascii=False)
    return dict(DEFAULT_CONFIG)


def enabled(value):
    if isinstance(value, str):
        return value.strip().lower() in {"1", "true", "yes", "on"}
    return bool(value)


def unit_setting(item, config, key, default):
    if item is not None and key in item:
        return int(item[key])
    if key in config:
        return int(config[key])
    return default


def configured_units(config):
    raw = config.get("units")
    if not raw:
        raise ExportError("No units configured; previous output kept.")
    units = []
    seen = set()
    for item in raw:
        name = str(item.get("name") or item.get("regos_unit") or "unit")
        if "regos_unit" not in item:
            raise ExportError(f"Unit {name} has no regos_unit; previous output kept.")
        if "department" not in item:
            raise ExportError(f"Unit {name} has no department; previous output kept.")
        regos_unit = int(item["regos_unit"])
        if regos_unit in seen:
            raise ExportError(f"REGOS unit {regos_unit} is listed twice; previous output kept.")
        seen.add(regos_unit)
        units.append({
            "name": name,
            "regos_unit": regos_unit,
            "weight_unit": unit_setting(item, config, "weight_unit", 0),
            "barcode_type": unit_setting(item, config, "barcode_type", 7),
            "label_id": unit_setting(item, config, "label_id", 1),
            "skip_invalid": bool(item.get("skip_invalid", False)),
            "department": int(item["department"]),
        })
    if not units:
        raise ExportError("No units configured; previous output kept.")
    return units


def clean_name(name, skip_invalid):
    item_name = "" if name is None else str(name).strip()
    if skip_invalid:
        item_name = " ".join(item_name.replace("\t", " ").replace("\r", " ").replace("\n", " ").split())
    if item_name == "" or "\t" in item_name or "\r" in item_name or "\n" in item_name:
        return None
    return item_name


def short_path(path):
    try:
        return win32api.GetShortPathName(path)
    except Exception as error:
        log(f"Short path was not available for the database ({error}).")
        return path


def price_amount(value):
    number = Decimal(0 if value is None else value)
    if number < 0:
        raise ExportError(f"Negative price {number}.")
    return number.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def format_price(value):
    return format(price_amount(value), "f").replace(".", ",")


def plu_code(raw):
    text = "" if raw is None else str(raw).strip()
    if not text.isdigit():
        raise ExportError(f"Item code {raw!r} is not a positive integer.")
    number = int(text)
    if number < 1:
        raise ExportError(f"Item code {raw!r} is not a positive integer.")
    return str(number)


def atomic_write(path, text):
    folder = os.path.dirname(path)
    if folder:
        os.makedirs(folder, exist_ok=True)
    temporary = path + "." + uuid.uuid4().hex + ".tmp"
    backup = path + ".previous"
    moved = False
    try:
        with open(temporary, "w", encoding="utf-8-sig", newline="") as handle:
            handle.write(text)
        if os.path.exists(path):
            os.replace(path, backup)
            moved = True
        os.replace(temporary, path)
    except Exception:
        if moved and not os.path.exists(path) and os.path.exists(backup):
            os.replace(backup, path)
        raise
    finally:
        if os.path.exists(temporary):
            try:
                os.remove(temporary)
            except OSError:
                pass


def acquire_single_instance():
    handle = win32event.CreateMutex(None, False, "Local\\REGOS_SyncTool_Watcher")
    if win32api.GetLastError() == winerror.ERROR_ALREADY_EXISTS:
        return None
    return handle


class Watcher:
    def __init__(self, config):
        self.config = config
        self.units = configured_units(config)
        self.update_sqlite = enabled(config.get("update_sqlite", False))
        self.check_time = int(config["check_time"])
        self.connection = None
        self.last_change = 0

    def connect(self):
        self.close()
        self.connection = fdb.connect(
            host=self.config["host"],
            database=short_path(self.config["database"]),
            user=self.config["user"],
            password=self.config["password"],
            charset="UTF8",
        )
        log("Connected to Firebird.")

    def close(self):
        if self.connection is not None:
            try:
                self.connection.close()
            except Exception:
                pass
            self.connection = None

    def _cursor(self):
        if self.connection is None:
            self.connect()
        return self.connection.cursor()

    def latest_change(self):
        cursor = self._cursor()
        try:
            cursor.execute(
                """
                SELECT FIRST 1 ITM_LAST_UPDATE
                FROM CTLG_ITM_ITEMS_REF
                ORDER BY ITM_LAST_UPDATE DESC
                """
            )
            item_row = cursor.fetchone()
            cursor.execute(
                """
                SELECT FIRST 1 PRC_LAST_UPDATE
                FROM CTLG_ITM_PRICES_REF
                ORDER BY PRC_LAST_UPDATE DESC
                """
            )
            price_row = cursor.fetchone()
            self.connection.commit()
        finally:
            cursor.close()
        stamps = []
        for row in (item_row, price_row):
            if row and row[0] is not None:
                stamps.append(row[0].timestamp())
        return max(stamps) if stamps else 0

    def fetch_items(self):
        unit_ids = [unit["regos_unit"] for unit in self.units]
        placeholders = ", ".join("?" for _ in unit_ids)
        cursor = self._cursor()
        try:
            cursor.execute(
                f"""
                SELECT CAST(I.ITM_CODE AS VARCHAR(20)), TRIM(I.ITM_NAME), P.PRC_VALUE, I.ITM_UNIT
                FROM CTLG_ITM_ITEMS_REF I
                LEFT JOIN CTLG_ITM_PRICES_REF P
                    ON I.ITM_ID = P.PRC_ITEM
                    AND P.PRC_PRICE_TYPE = ?
                WHERE I.ITM_DELETED_MARK = 0
                    AND I.ITM_UNIT IN ({placeholders})
                ORDER BY I.ITM_ID
                """,
                (int(self.config["price_type"]), *unit_ids),
            )
            rows = cursor.fetchall()
            self.connection.commit()
        finally:
            cursor.close()
        return rows

    def build_file(self, rows):
        if not rows:
            raise ExportError("No items; previous output kept.")
        by_regos = {unit["regos_unit"]: unit for unit in self.units}
        seen = set()
        counts = {unit["name"]: 0 for unit in self.units}
        skipped = []
        zero_codes = []
        zero_seen = set()
        records = []
        lines = ["\t".join(COLUMNS) + "\t"]
        for code, name, price, regos_unit in rows:
            unit = by_regos[int(regos_unit)]
            try:
                plu = plu_code(code)
                amount = price_amount(price)
                item_name = None if amount == 0 else clean_name(name, unit["skip_invalid"])
                if amount != 0 and item_name is None:
                    raise ExportError(f"Invalid name for PLU {plu}")
                unit_price = None if amount == 0 else format(amount, "f").replace(".", ",")
            except ExportError as error:
                if unit["skip_invalid"]:
                    skipped.append(f"{unit['name']} {code}: {error}")
                    continue
                raise ExportError(f"{error} Previous output kept.")
            if plu in seen or plu in zero_seen:
                raise ExportError(f"Duplicate PLU {plu}; previous output kept.")
            if amount == 0:
                zero_seen.add(plu)
                zero_codes.append(plu)
                continue
            seen.add(plu)
            counts[unit["name"]] += 1
            values = dict(DEFAULTS)
            values["LFCode"] = plu
            values["ItemCode"] = plu
            values["Name1"] = item_name
            values["Department"] = str(unit["department"])
            values["BarcodeType1"] = str(unit["barcode_type"])
            values["WeightUnit"] = str(unit["weight_unit"])
            values["Label1"] = str(unit["label_id"])
            values["UnitPrice"] = unit_price
            lines.append("\t".join(values[column] for column in COLUMNS) + "\t")
            records.append(self.sqlite_record(values))
        if not seen and not zero_codes:
            raise ExportError("No valid items; previous output kept.")
        return "\r\n".join(lines) + "\r\n", counts, skipped, records, zero_codes

    def sqlite_record(self, values):
        record = {}
        for column in COLUMNS:
            if column in SQLITE_DATE:
                record[column] = SQLITE_DATE_SENTINEL
            elif column == "UpdateTime":
                record[column] = None
            elif column in SQLITE_TEXT:
                record[column] = values[column]
            elif column in SQLITE_FLOAT:
                record[column] = float(str(values[column]).replace(",", "."))
            else:
                record[column] = int(values[column])
        return record

    def write_sqlite(self, records, remove_codes):
        path = self.config.get("synctool_database") or ""
        if not path or not os.path.isfile(path):
            raise ExportError(f"SyncTool database was not found: {path}")
        updated_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        for record in records:
            record["UpdateTime"] = updated_at
        assignments = ", ".join(
            f"{column}=excluded.{column}" for column in COLUMNS if column != "LFCode"
        )
        sql = (
            f"INSERT INTO PLUTbl ({', '.join(COLUMNS)}) "
            f"VALUES ({', '.join('?' for _ in COLUMNS)}) "
            f"ON CONFLICT(LFCode) DO UPDATE SET {assignments}"
        )
        parameters = [tuple(record[column] for column in COLUMNS) for record in records]
        connection = sqlite3.connect(path, timeout=30)
        try:
            connection.execute("BEGIN IMMEDIATE")
            if parameters:
                connection.executemany(sql, parameters)
            for start in range(0, len(remove_codes), 500):
                chunk = [int(code) for code in remove_codes[start:start + 500]]
                placeholders = ", ".join("?" for _ in chunk)
                connection.execute(
                    f"DELETE FROM PLUTbl WHERE LFCode IN ({placeholders})",
                    chunk,
                )
            connection.commit()
        except Exception:
            try:
                connection.rollback()
            except Exception:
                pass
            raise
        finally:
            connection.close()
        return path, len(records)

    def export(self, force):
        latest = self.latest_change()
        if not force and self.last_change and latest <= self.last_change:
            return False
        text, counts, skipped, records, zero_codes = self.build_file(self.fetch_items())
        destination = self.config["plu_file_path"]
        atomic_write(destination, text)
        summary = ", ".join(f"{count} {name}" for name, count in counts.items())
        details = ", ".join(
            f"{unit['name']} department={unit['department']} barcode={unit['barcode_type']} "
            f"unit={unit['weight_unit']} label={unit['label_id']}"
            for unit in self.units
        )
        log(f"OK: {summary}. PLU=ItemCode, {details}. Output: {destination}")
        if zero_codes:
            log(f"Skipped {len(zero_codes)} zero prices.")
        if skipped:
            log(f"Skipped {len(skipped)} invalid rows. " + " | ".join(skipped))
        if self.update_sqlite:
            try:
                path, count = self.write_sqlite(records, zero_codes)
            except Exception as error:
                log(f"ERROR: SyncTool database was not updated ({error}).")
                return False
            removed = f", removed {len(zero_codes)} zero prices" if zero_codes else ""
            log(f"OK: SyncTool database updated ({count} PLU{removed}). {path}")
        self.last_change = latest
        return True

    def run_forever(self):
        log("Starting watcher.")
        while True:
            try:
                self.export(force=False)
            except ExportError as error:
                log(f"ERROR: {error}")
            except Exception as error:
                log(f"ERROR: {error}")
                self.close()
            time.sleep(max(self.check_time, 1))


def main():
    argument = sys.argv[1] if len(sys.argv) > 1 else ""
    if argument not in ("", "once"):
        log(f"Invalid argument: {argument}. Use no argument to watch, or 'once' to write one file.")
        return 2

    mutex = None
    if argument != "once":
        mutex = acquire_single_instance()
        if mutex is None:
            log("Watcher already running.")
            return 0

    watcher = Watcher(load_config())
    try:
        if argument == "once":
            watcher.connect()
            watcher.export(force=True)
            return 0
        watcher.run_forever()
        return 0
    except ExportError as error:
        log(f"ERROR: {error}")
        return 1
    except Exception as error:
        log(f"ERROR: {error}")
        return 1
    finally:
        watcher.close()
        if mutex is not None:
            win32event.ReleaseMutex(mutex)
            win32api.CloseHandle(mutex)


if __name__ == "__main__":
    sys.exit(main())
