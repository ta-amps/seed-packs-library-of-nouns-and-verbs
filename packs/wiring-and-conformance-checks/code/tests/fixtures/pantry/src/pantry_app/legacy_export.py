"""The old spreadsheet export, replaced by pantry_app.exporters and never removed."""


def export_rows(rows):
    return [",".join(str(value) for value in row.values()) for row in rows]
