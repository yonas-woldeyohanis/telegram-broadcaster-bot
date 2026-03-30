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
                    chat_title TEXT,
                    is_active INTEGER DEFAULT 1
                )
            """)

    def add_group(self, chat_id, title):
        with self.connection:
            return self.cursor.execute("INSERT OR REPLACE INTO groups (chat_id, chat_title) VALUES (?, ?)", (chat_id, title))

    def toggle_group(self, chat_id):
        with self.connection:
            return self.cursor.execute("UPDATE groups SET is_active = 1 - is_active WHERE chat_id = ?", (chat_id,))

    def set_all_status(self, status: int):
        with self.connection:
            return self.cursor.execute("UPDATE groups SET is_active = ?", (status,))

    def get_all_groups(self, only_active=False):
        with self.connection:
            if only_active:
                return self.cursor.execute("SELECT chat_id, chat_title FROM groups WHERE is_active = 1").fetchall()
            return self.cursor.execute("SELECT chat_id, chat_title, is_active FROM groups").fetchall()