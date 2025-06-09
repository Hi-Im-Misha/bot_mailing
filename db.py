import sqlite3
import os
import json

DB_PATH = 'sent_posts.db'


def init_db():
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    with conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS sent_posts (
                user_id INTEGER NOT NULL,
                post_id INTEGER NOT NULL,
                PRIMARY KEY(user_id, post_id)
            )
            """
        )
    return conn


def load_sent_posts(conn):
    sent = {}
    cursor = conn.execute('SELECT user_id, post_id FROM sent_posts')
    for user_id, post_id in cursor.fetchall():
        sent.setdefault(user_id, set()).add(post_id)
    return sent


def add_sent_post(conn, user_id, post_id):
    with conn:
        conn.execute(
            'INSERT OR IGNORE INTO sent_posts (user_id, post_id) VALUES (?, ?)',
            (user_id, post_id),
        )


def migrate_from_json(conn, json_path):
    if not os.path.exists(json_path):
        return
    with open(json_path, 'r', encoding='utf-8') as f:
        try:
            data = json.load(f)
        except json.JSONDecodeError:
            data = {}
    for uid_str, posts in data.items():
        uid = int(uid_str)
        for pid in posts:
            try:
                pid_int = int(pid)
            except ValueError:
                continue
            add_sent_post(conn, uid, pid_int)
    os.remove(json_path)