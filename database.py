import sqlite3

class Database:
    def __init__(self, db_file):
        self.connection = sqlite3.connect(db_file)
        self.cursor = self.connection.cursor()
        self.create_table()

    def create_table(self):
        with self.connection:
            # Groups table
            self.cursor.execute("""
                CREATE TABLE IF NOT EXISTS groups (
                    chat_id INTEGER PRIMARY KEY,
                    chat_title TEXT,
                    is_active INTEGER DEFAULT 0
                )
            """)
            # Global Stats table
            self.cursor.execute("""
                CREATE TABLE IF NOT EXISTS stats (
                    id INTEGER PRIMARY KEY,
                    total_broadcasts INTEGER DEFAULT 0,
                    total_messages_delivered INTEGER DEFAULT 0
                )
            """)
            # Initialize stats row if empty
            self.cursor.execute("INSERT OR IGNORE INTO stats (id, total_broadcasts, total_messages_delivered) VALUES (1, 0, 0)")

    def add_group(self, chat_id, title):
        with self.connection:
            return self.cursor.execute("INSERT OR REPLACE INTO groups (chat_id, chat_title) VALUES (?, ?)", (chat_id, title))

    def remove_group(self, chat_id):
        with self.connection:
            return self.cursor.execute("DELETE FROM groups WHERE chat_id = ?", (chat_id,))

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

    def update_broadcast_stats(self, delivered_count):
        with self.connection:
            self.cursor.execute("UPDATE stats SET total_broadcasts = total_broadcasts + 1, total_messages_delivered = total_messages_delivered + ?", (delivered_count,))

    def get_global_stats(self):
        with self.connection:
            return self.cursor.execute("SELECT total_broadcasts, total_messages_delivered FROM stats WHERE id = 1").fetchone()