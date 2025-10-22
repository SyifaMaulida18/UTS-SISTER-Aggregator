Keputusan Desain

2.1 Idempotency
Konsep idempotency digunakan agar sistem tidak memproses ulang event yang sama saat terjadi retry atau duplicate publish. Implementasi dilakukan dengan menyimpan event_id di dalam basis data SQLite. Setiap kali consumer memproses event baru, sistem akan mengeksekusi operasi INSERT dengan UNIQUE constraint pada kolom topic dan event_id. Jika terjadi IntegrityError, event dianggap duplikat dan diabaikan.
Pendekatan ini menjamin bahwa hasil akhir sistem akan tetap konsisten (eventual consistency) tanpa kehilangan performa secara signifikan (Coulouris et al., 2011, Chap. 3).

2.2 Dedup Store
Deduplication store dibangun menggunakan SQLite + Docker Volume untuk menjamin persistensi data. Dengan volume mount ke direktori host (/app/data), file database events.db tetap utuh meskipun container restart.
Pendekatan ini lebih efisien daripada penyimpanan in-memory karena state deduplication bersifat durable dan tidak hilang saat sistem gagal.

2.3 Ordering
Sistem hanya menjamin per-partition ordering—yakni, urutan lokal antar event dengan topic yang sama. Pendekatan ini mengikuti prinsip bahwa total ordering tidak selalu diperlukan dalam sistem log aggregator, karena menambah overhead sinkronisasi global (van Steen & Tanenbaum, 2023, Chap. 5).
Untuk menjaga urutan lokal, event_id disusun dengan format <UUIDv4>-<timestamp>-<counter>, memungkinkan konsistensi kausal menggunakan timestamp sorting sederhana.

2.4 Retry Mechanism
Mekanisme retry diterapkan pada publisher dengan kebijakan exponential backoff. Jika pengiriman gagal akibat koneksi atau error internal, sistem akan menunggu secara bertahap sebelum mengirim ulang. Di sisi consumer, idempotency memastikan retry tidak menyebabkan duplikasi hasil.
Pendekatan ini selaras dengan prinsip mitigasi kegagalan (failure mitigation) yang dijelaskan oleh van Steen & Tanenbaum (2023, Chap. 6).
