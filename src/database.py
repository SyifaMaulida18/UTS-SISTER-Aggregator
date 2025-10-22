# src/database.py
import aiosqlite
import logging

# Tentukan path database. Ini akan mengarah ke volume /app/data/ di dalam Docker
DB_PATH = "/app/data/events.db"
# Untuk testing lokal (di luar docker), Anda mungkin ingin menggantinya sementara:
# DB_PATH = "./data/events.db"

log = logging.getLogger("uvicorn")

async def init_db():
    """Inisialisasi database dan tabel (menggunakan koneksi sementara)."""
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("""
            CREATE TABLE IF NOT EXISTS processed_events (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                topic TEXT NOT NULL,
                event_id TEXT NOT NULL,
                processed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(topic, event_id)
            )
        """)
        await db.commit()
        log.info("Database initialized.")

async def mark_event_processed(db_conn: aiosqlite.Connection, topic: str, event_id: str) -> bool:
    """
    Mencoba mencatat event MENGGUNAKAN KONEKSI YANG SUDAH ADA.
    Mengembalikan True jika event baru (berhasil INSERT).
    Mengembalikan False jika event duplikat (gagal INSERT karena UNIQUE constraint).
    """
    try:
        # Kita gunakan koneksi yang di-pass sebagai argumen
        await db_conn.execute(
            "INSERT INTO processed_events (topic, event_id) VALUES (?, ?)",
            (topic, event_id)
        )
        await db_conn.commit() # Commit di setiap insert
        return True  # Berhasil insert, event ini unik
    except aiosqlite.IntegrityError:
        # Ini terjadi jika (topic, event_id) sudah ada (pelanggaran UNIQUE)
        return False # Gagal insert, event ini duplikat
    # Biarkan error lain (spt 'locked') 'naik' untuk ditangani consumer