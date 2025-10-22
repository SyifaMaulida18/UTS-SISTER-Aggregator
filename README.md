Event Aggregator Service (uts-aggregator)
Layanan aggregator event yang idempotent dan persisten dibangun menggunakan FastAPI, SQLite, dan Docker.

Prerequisites
Docker

Python 3.11+ (untuk development lokal dan testing)

PowerShell

Dependensi Python utama (dikelola oleh requirements.txt dan Dockerfile):

fastapi

uvicorn[standard]

pydantic

aiosqlite

pytest

httpx

Build dan Run (Docker)
Semua perintah dijalankan menggunakan PowerShell dari root folder proyek.

1. Build Docker Image
PowerShell

docker build -t uts-aggregator .
2. Run Docker Container
Perintah ini menjalankan container dan me-mount folder ./data lokal ke /app/data di dalam container untuk persistensi database SQLite.

PowerShell

docker run -d `
  -p 8080:8080 `
  --name my-aggregator `
  -v ${PWD}/data:/app/data `
  uts-aggregator
3. Cek Log (Opsional)
PowerShell

docker logs -f my-aggregator
4. Stop dan Hapus Container
PowerShell

docker stop my-aggregator
docker rm my-aggregator
API Endpoints
POST /publish
Menerima satu atau batch event untuk diproses.

Body (Single): Event

Body (Batch): List[Event]

Respon Sukses: 202Accepted

Skema Event (Contoh):

JSON

{
  "topic": "string",
  "event_id": "string (uuid)",
  "source": "string",
  "payload": { "key": "value" }
}
GET /events
Mengembalikan daftar event unik yang telah berhasil diproses.

Query Parameter (Opsional): topic (string) - Untuk filter berdasarkan topic.

Respon Sukses: 200 OK

GET /stats
Menampilkan statistik operasional layanan.

Respon Sukses: 200 OK

Contoh Penggunaan (PowerShell)
1. Siapkan Payload
PowerShell

$eventJson = @'
{
  "topic": "pembayaran",
  "event_id": "evt_abc_123", 
  "source": "powershell_test",
  "payload": { "amount": 50000, "user_id": "u_001" }
}
'@
2. Kirim Event (Unik dan Duplikat)
Kirim event pertama kali:

PowerShell

Invoke-RestMethod -Uri http://localhost:8080/publish -Method Post -Body $eventJson -ContentType "application/json"
Kirim event yang sama (duplikat):

PowerShell

Invoke-RestMethod -Uri http://localhost:8080/publish -Method Post -Body $eventJson -ContentType "application/json"
3. Periksa Statistik
PowerShell

Invoke-RestMethod -Uri http://localhost:8080/stats
Output akan menunjukkan received: 2, unique_processed: 1, dan duplicate_dropped: 1.

4. Uji Persistensi (Restart)
Matikan container:

PowerShell

docker stop my-aggregator
docker rm my-aggregator
Nyalakan container baru (akan membaca file DB dari volume):

PowerShell

docker run -d `
  -p 8080:8080 `
  --name my-aggregator `
  -v ${PWD}/data:/app/data `
  uts-aggregator
Kirim lagi event duplikat:

PowerShell

Invoke-RestMethod -Uri http://localhost:8080/publish -Method Post -Body $eventJson -ContentType "application/json"
Cek statistik lagi:

PowerShell

Invoke-RestMethod -Uri http://localhost:8080/stats
Output akan menunjukkan received: 1 tapi unique_processed: 0 dan duplicate_dropped: 1, membuktikan state persistensi bekerja.

Development & Testing Lokal
1. Setup Virtual Environment
PowerShell

python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
2. Jalankan Unit Tests
Pastikan venv aktif.

PowerShell

pytest
3. Jalankan Stress Test
Pastikan container sedang berjalan (docker run ...) dan venv aktif.

PowerShell

python .\run_performance_test.py
