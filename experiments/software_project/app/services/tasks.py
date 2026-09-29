def create(database, title):
    if not title or not title.strip():
        raise ValueError("task title must not be blank")
    cursor = database.execute("INSERT INTO tasks(title, done) VALUES (?, 0)", (title.strip(),))
    return cursor.lastrowid


def list_tasks(database):
    return [
        {"id": row[0], "title": row[1], "done": bool(row[2])}
        for row in database.execute("SELECT id, title, done FROM tasks ORDER BY id")
    ]
