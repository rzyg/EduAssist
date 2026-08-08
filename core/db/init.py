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

        # 创建节假日数据表
        # 年 + 月日 唯一，索引 id 依次递增
        conn.execute("""
            CREATE TABLE IF NOT EXISTS holiday (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                year INTEGER NOT NULL,
                month_day TEXT NOT NULL,
                holiday INTEGER NOT NULL,
                leave_school INTEGER NOT NULL DEFAULT 0,
                return_school INTEGER NOT NULL DEFAULT 0,
                schedule_modification TEXT,
                remark TEXT,
                UNIQUE(year, month_day)
            )
        """)


if __name__ == "__main__":
    initDatabase()
