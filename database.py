import sqlite3

class Database:
    def __init__(self, db_file):
        self.connection = sqlite3.connect(db_file)
        self.cursor = self.connection.cursor()
        self.create_table()

    def create_table(self):
        with self.connection:
            self.cursor.execute("""
                CREATE TABLE IF NOT EXISTS groups (
                    chat_id INTEGER PRIMARY KEY,
                    chat_title TEXT
                )
            """)

    def add_group(self, chat_id, title):
        with self.connection:
            return self.cursor.execute("INSERT OR IGNORE INTO groups (chat_id, chat_title) VALUES (?, ?)", (chat_id, title))

    def remove_group(self, chat_id):
        with self.connection:
            return self.cursor.execute("DELETE FROM groups WHERE chat_id = ?", (chat_id,))

    def get_all_groups(self):
        with self.connection:
            return self.cursor.execute("SELECT chat_id FROM groups").fetchall()