# run_performance_test.py
import asyncio
import httpx
import time
import uuid
import random

# --- Konfigurasi ---
TOTAL_EVENTS = 5000
DUPLICATE_PERCENTAGE = 0.2  # 20%
CONCURRENT_REQUESTS = 100
API_URL = "http://localhost:8080/publish"
STATS_URL = "http://localhost:8080/stats"
# <--- PERUBAHAN: Naikkan timeout ke 5 menit (300 detik)
POLLING_TIMEOUT_SECONDS = 300
# --------------------

def generate_events():
    """Membangkitkan daftar event, termasuk duplikat."""
    print("Membangkitkan event payload...")
    
    num_duplicates = int(TOTAL_EVENTS * DUPLICATE_PERCENTAGE)
    num_unique = TOTAL_EVENTS - num_duplicates
    
    events_to_send = []
    # <--- PERUBAHAN: Kita simpan event unik di sini
    unique_events_for_duplication = [] 

    # 1. Buat event-event unik
    for i in range(num_unique):
        topic = f"topic_{i % 10}"
        event_id = str(uuid.uuid4())
        event = {
            "topic": topic,
            "event_id": event_id,
            "source": "perf_test",
            "payload": {"value": i}
        }
        events_to_send.append(event)
        unique_events_for_duplication.append(event) # <--- PERUBAHAN: Simpan event
        
    # 2. Buat event-event duplikat
    for _ in range(num_duplicates):
        # <--- PERUBAHAN: Ambil event acak dan salin (topic DAN event_id)
        event_to_duplicate = random.choice(unique_events_for_duplication)
        
        duplicate_event = {
            "topic": event_to_duplicate["topic"],       # Salin topic
            "event_id": event_to_duplicate["event_id"], # Salin event_id
            "source": "perf_test_dup",
            "payload": {"value": -1}
        }
        events_to_send.append(duplicate_event)
        
    random.shuffle(events_to_send)
    print(f"Total {len(events_to_send)} event siap dikirim.")
    print(f"({num_unique} unik, {num_duplicates} duplikat YANG BENAR)") # <--- PERUBAHAN
    return events_to_send

async def send_event(client, event):
    """Mengirim satu event ke API."""
    try:
        response = await client.post(API_URL, json=event)
        response.raise_for_status()
        return True
    except httpx.HTTPError as e:
        print(f"Request gagal: {e}")
        return False

async def main():
    """Fungsi utama untuk menjalankan stress test."""
    events = generate_events()
    expected_unique = TOTAL_EVENTS - int(TOTAL_EVENTS * DUPLICATE_PERCENTAGE)
    expected_duplicates = int(TOTAL_EVENTS * DUPLICATE_PERCENTAGE)
    
    print(f"\nMemulai stress test dengan {CONCURRENT_REQUESTS} request konkuren...")
    start_time = time.time()
    
    async with httpx.AsyncClient(timeout=10.0) as client:
        tasks = []
        for event in events:
            tasks.append(send_event(client, event))
            
            if len(tasks) >= CONCURRENT_REQUESTS:
                await asyncio.gather(*tasks)
                tasks = []
        
        if tasks:
            await asyncio.gather(*tasks)

    end_time = time.time()
    total_time = end_time - start_time
    
    print("\n--- Hasil Uji Performa (Pengiriman) ---")
    print(f"Total event terkirim: {TOTAL_EVENTS}")
    print(f"Total waktu kirim: {total_time:.2f} detik")
    print(f"Requests per detik (RPS): {(TOTAL_EVENTS / total_time):.2f}")

    print("\nMenunggu server menyelesaikan pemrosesan (queue size)...")
    final_stats = {}
    polling_start_time = time.time()
    try:
        async with httpx.AsyncClient() as client:
            while True:
                stats_response = await client.get(STATS_URL)
                stats = stats_response.json()
                queue_size = stats.get("queue_size_approx", -1)
                
                if queue_size == 0:
                    print("Queue kosong. Pemrosesan selesai.")
                    final_stats = stats
                    break
                
                # <--- PERUBAHAN: Logging lebih detail
                print(f"Ukuran antrian saat ini: {queue_size} | Unik: {stats['unique_processed']} | Duplikat: {stats['duplicate_dropped']}. Menunggu 2 detik...")
                await asyncio.sleep(2)
                
                # <--- PERUBAHAN: Gunakan timeout baru
                if (time.time() - polling_start_time) > POLLING_TIMEOUT_SECONDS:
                    print(f"Gagal menunggu queue kosong setelah {POLLING_TIMEOUT_SECONDS} detik.")
                    final_stats = stats
                    break
    except httpx.HTTPError as e:
        print(f"Gagal mengambil stats saat polling: {e}")
        return

    print("\n--- Verifikasi Server Stats (Setelah Queue Kosong) ---")
    try:
        stats = final_stats
        if not stats:
             raise Exception("Gagal mendapatkan stats final")
            
        print(f"Uptime server: {stats['uptime_seconds']:.2f} detik")
        print(f"Total diterima (server): {stats['received']}")
        print(f"Total unik diproses (server): {stats['unique_processed']}")
        print(f"Total duplikat di-drop (server): {stats['duplicate_dropped']}")
        
        assert stats['received'] == TOTAL_EVENTS
        assert stats['unique_processed'] == expected_unique
        assert stats['duplicate_dropped'] == expected_duplicates
        
        print(f"\n✅ Verifikasi berhasil! Server memproses {stats['unique_processed']} unik dan {stats['duplicate_dropped']} duplikat.")
        
    except AssertionError:
        print("\n❌ VERIFIKASI GAGAL:")
        print(f"  Diterima:   Expected {TOTAL_EVENTS}, Got {stats['received']}")
        print(f"  Unik:       Expected {expected_unique}, Got {stats['unique_processed']}")
        print(f"  Duplikat:   Expected {expected_duplicates}, Got {stats['duplicate_dropped']}")
    except Exception as e:
        print(f"Gagal memverifikasi stats: {e}")

if __name__ == "__main__":
    asyncio.run(main())