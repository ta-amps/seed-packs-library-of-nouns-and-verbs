def write(rows):
    return "\n".join(row["when"] for row in rows)
