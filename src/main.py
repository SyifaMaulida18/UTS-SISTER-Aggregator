# src/main.py
import asyncio
import logging
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from typing import List, Union, Dict, Any
from uuid import uuid4

import aiosqlite # <--- IMPORT aiosqlite
from fastapi import FastAPI, Query
from pydantic import BaseModel, Field

# Import modul database kita
from . import database

# --- Konfigurasi Logging ---
logging.basicConfig(level=logging.INFO)
log = logging.getLogger("uvicorn.error")

# --- Model Data (Pydantic) ---
class Event(BaseModel):
    topic: str
    event_id: str = Field(default_factory=lambda: str(uuid4()))
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    source: str
    payload: Dict[str, Any]

# --- Penyimpanan In-Memory ---
event_queue = asyncio.Queue()
app_stats = {
    "received": 0,
    "unique_processed": 0,
    "duplicate_dropped": 0,
    "topics": set(),
}
processed_events_store: List[Event] = []
start_time = datetime.now(timezone.utc)


# --- Background Worker (Consumer) ---
async def event_consumer():
    """Membaca event dari antrian internal dan memprosesnya."""
    log.info("Event consumer started...")
    
    db_conn = None
    try:
        # <--- PERUBAHAN: Buka KONEKSI SATU KALI DI SINI
        db_conn = await aiosqlite.connect(database.DB_PATH)
        log.info("Consumer established persistent DB connection.")
        
        while True:
            event = None  # Definisikan di luar try
            try:
                # 1. Ambil event dari antrian
                event = await event_queue.get()
                
                # 2. Cek & catat (passing koneksi yang sudah ada)
                is_new = await database.mark_event_processed(db_conn, event.topic, event.event_id)
                
                if is_new:
                    # 3. Jika Unik: proses event
                    app_stats["unique_processed"] += 1
                    app_stats["topics"].add(event.topic)
                    processed_events_store.append(event)
                    # log.info(f"Processed new event (ID: {event.event_id}, Topic: {event.topic})") # <-- Terlalu 'berisik' untuk 5000 event
                else:
                    # 4. Jika Duplikat: drop
                    app_stats["duplicate_dropped"] += 1
                    # log.warning(f"Dropped duplicate event (ID: {event.event_id}, Topic: {event.topic})") # <-- Terlalu 'berisik'
                        
            except aiosqlite.IntegrityError:
                # Seharusnya sudah ditangani di database.py, tapi untuk jaga-jaga
                log.warning(f"IntegrityError race condition for {event.event_id if event else 'UNKNOWN'}")
                if event:
                    app_stats["duplicate_dropped"] += 1
            except Exception as e:
                log.error(f"Error in consumer processing loop: {e} for event {event.event_id if event else 'UNKNOWN'}")
                # Jangan increment stats, kita tidak tahu statusnya
            finally:
                if event:
                    # Penting untuk menandai tugas selesai
                    event_queue.task_done()

    except Exception as e:
        log.error(f"FATAL: Event consumer failed to connect to DB: {e}")
    finally:
        if db_conn:
            await db_conn.close()
            log.info("Consumer closed DB connection.")


# --- Daur Hidup Aplikasi (Startup/Shutdown) ---
@asynccontextmanager
async def lifespan(app: FastAPI):
    # --- Startup ---
    log.info("Application startup...")
    # 1. Inisialisasi (membuat tabel jika belum ada)
    await database.init_db()
    # 2. Jalankan background worker
    asyncio.create_task(event_consumer())
    
    yield  # Aplikasi berjalan di sini
    
    # --- Shutdown ---
    log.info("Application shutdown...")


# --- Inisialisasi Aplikasi FastAPI ---
app = FastAPI(
    title="Event Aggregator Service",
    lifespan=lifespan
)

# --- Endpoint API ---
@app.post("/publish", status_code=202)
async def publish_events(data: Union[Event, List[Event]]):
    """Menerima satu atau batch event dan memasukkannya ke antrian internal."""
    events = data if isinstance(data, list) else [data]
    
    for event in events:
        await event_queue.put(event)
        app_stats["received"] += 1
        
    return {"message": f"Accepted {len(events)} event(s) for processing."}

@app.get("/events")
async def get_processed_events(topic: str = Query(None)):
    """Mengembalikan daftar event unik yang telah diproses."""
    if topic:
        return [e for e in processed_events_store if e.topic == topic]
    return processed_events_store

@app.get("/stats")
async def get_stats():
    """Menampilkan statistik operasional layanan."""
    uptime_delta = datetime.now(timezone.utc) - start_time
    return {
        "uptime_seconds": uptime_delta.total_seconds(),
        "received": app_stats["received"],
        "unique_processed": app_stats["unique_processed"],
        "duplicate_dropped": app_stats["duplicate_dropped"],
        "queue_size_approx": event_queue.qsize(),
        "topics": list(app_stats["topics"])
    }