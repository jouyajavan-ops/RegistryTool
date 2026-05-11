import csv
import sqlite3
from pathlib import Path

script_path = Path(__file__).resolve()
base_path = script_path.parent.parent

exports_path = base_path / "exports"
db_path = base_path / "database" / "drawing_registry.db"

project_name = "Hinkler"

csv_files = list(exports_path.glob("revit_sheets_export_*.csv"))

if not csv_files:
    print("No export CSV files found.")
    raise SystemExit

latest_csv = max(csv_files, key=lambda p: p.stat().st_mtime)

print("Importing:", latest_csv)
print("Project:", project_name)

conn = sqlite3.connect(db_path)
cursor = conn.cursor()

with open(latest_csv, "r", newline="", encoding="utf-8-sig") as csvfile:
    reader = csv.DictReader(csvfile)

    inserted_count = 0
    updated_count = 0

    for row in reader:
        sheet_number = row.get("sheet_number", "")

        cursor.execute("""
            SELECT id FROM drawings
            WHERE project_name = ? AND sheet_number = ?
        """, (project_name, sheet_number))

        existing = cursor.fetchone()

        if existing:
            cursor.execute("""
                UPDATE drawings
                SET
                    model_name = ?,
                    sheet_name = ?,
                    current_revision = ?,
                    revision_date = ?,
                    revision_description = ?,
                    last_updated = CURRENT_TIMESTAMP
                WHERE project_name = ? AND sheet_number = ?
            """, (
                row.get("model_name", ""),
                row.get("sheet_name", ""),
                row.get("current_revision", ""),
                row.get("revision_date", ""),
                row.get("revision_description", ""),
                project_name,
                sheet_number
            ))

            updated_count += 1

        else:
            cursor.execute("""
                INSERT INTO drawings (
                    project_name,
                    model_name,
                    sheet_number,
                    sheet_name,
                    current_revision,
                    revision_date,
                    revision_description,
                    issue_status,
                    assigned_to,
                    progress_status,
                    package_name,
                    regulated_required,
                    regulated_rev,
                    regulated_date,
                    regulated_description,
                    regulated_dp_name,
                    regulated_dp_reg_no
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                project_name,
                row.get("model_name", ""),
                sheet_number,
                row.get("sheet_name", ""),
                row.get("current_revision", ""),
                row.get("revision_date", ""),
                row.get("revision_description", ""),
                "",
                "",
                "Not Started",
                "",
                row.get("regulated_required", "No"),
                row.get("regulated_rev", ""),
                row.get("regulated_date", ""),
                row.get("regulated_description", ""),
                row.get("regulated_dp_name", ""),
                row.get("regulated_dp_reg_no", "")
            ))

            inserted_count += 1

conn.commit()
conn.close()

print("Import complete.")
print("Inserted:", inserted_count)
print("Updated:", updated_count)