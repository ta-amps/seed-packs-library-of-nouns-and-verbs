"""A tiny in-memory store standing in for a database."""


class Store:
    def __init__(self, path):
        self.path = path
        self.rows = []

    def save(self, row):
        self.rows.append(row)
        return row

    def delete(self, when):
        before = len(self.rows)
        self.rows = [row for row in self.rows if row["when"] != when]
        return before - len(self.rows)

    def ping(self):
        return self.path is not None
