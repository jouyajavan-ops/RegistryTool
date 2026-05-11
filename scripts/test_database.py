import sqlite3
from pathlib import Path

db_path = Path(r"E:\Projects\2026\Landmark\RevitRegistryTool\database\drawing_registry.db")

conn = sqlite3.connect(db_path)
cursor = conn.cursor()

cursor.execute("""
INSERT INTO drawings (
    model_name,
    sheet_number,
    sheet_name,
    current_revision,
    revision_date,
    revision_description,
    issue_status,
    assigned_to,
    progress_status,
    package_name
)
VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
""", (
    "Test Revit Model",
    "A-1001",
    "Ground Floor Plan",
    "C01",
    "2026-05-11",
    "Issued for CC",
    "In Progress",
    "Jouya",
    "50%",
    "CC Package 01"
))

conn.commit()

cursor.execute("SELECT sheet_number, sheet_name, current_revision, assigned_to FROM drawings;")
rows = cursor.fetchall()

print("Drawings in database:")
for row in rows:
    print(row)

conn.close()