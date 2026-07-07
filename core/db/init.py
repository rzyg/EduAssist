def initDatabase():
    import sqlite3
    from pathlib import Path
    from core.config import DATA_DIR

    # 确保目录存在
    dataDir = DATA_DIR
    dataDir.mkdir(parents=True, exist_ok=True)
    databasePath = dataDir / "data.db"

    with sqlite3.connect(databasePath) as conn:
        # 创建用户数据表
        conn.execute("""
            CREATE TABLE IF NOT EXISTS user (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT NOT NULL,
                phone TEXT NOT NULL,
                identity TEXT NOT NULL
            )
        """)


if __name__ == "__main__":
    initDatabase()
