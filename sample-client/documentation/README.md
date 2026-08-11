# Panduan Konfigurasi JSON untuk Sample Client

Sample Client (CLI) mendukung mode _Batch Import_ menggunakan konfigurasi file JSON. File JSON ini berfungsi untuk memberikan instruksi kepada backend FastAPI terkait Novel yang akan ditranslasi, Chapter mana yang akan diproses, Model & Platform AI yang akan dipakai, serta pengaturan (Settings) lainnya.

Anda dapat menjalankan file konfigurasi json melalui Command Line:
```bash
uv run python main.py <nama_file.json>
# Contoh: uv run python main.py series.json
```

## Fitur Pengecekan Duplikat dan Retry Cerdas
Mulai versi terbaru, jika Anda mengirim konfigurasi untuk chapter yang **sudah ada di database**, sistem akan menerapkan kondisi berikut:

1. **Chapter Status 'failed'**: Jika chapter sebelumnya gagal (failed), maka otomatis sistem akan menerima dan meretry chapter tersebut.
2. **Platform/Model Baru**: Jika chapter berstatus 'translated', tetapi Anda mengirim konfigurasi dengan Model atau Platform AI yang *berbeda* dengan yang sebelumnya menerjemahkan chapter ini, maka sistem akan mengizinkan proses berjalan untuk ditranslasi menggunakan model baru tersebut.
3. **Multi-Model**: Anda dapat menginput *beberapa model* sekaligus di dalam array `models`. Sistem akan otomatis membagi tugas ini (seperti fitur retry multi model) ke semua model yang ditentukan.

## Contoh File Konfigurasi

Beberapa file contoh disertakan dalam direktori ini:
- `example_failed_only.json`: Contoh cara membuat request ulang hanya untuk melanjutkan Chapter tertentu.
- `example_new_platform.json`: Contoh menggunakan platform dan API Key khusus untuk 1 model (misalnya mencoba API provider baru).
- `example_multi_model.json`: Contoh memasukkan banyak model sekaligus dalam satu `platform`. Hal ini akan membuat backend menjalankan Job untuk masing-masing model yang terdaftar pada waktu bersamaan (Sangat berguna untuk komparasi).
