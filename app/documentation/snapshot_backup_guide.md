# Panduan Backup & Restore (Snapshot Database)

Aplikasi ini memiliki fitur **Snapshot API** bawaan yang memungkinkan kamu untuk melakukan *backup* dan *restore* seluruh database (termasuk chapter, karakter, dan job) tanpa perlu mematikan server (mendukung *online backup/restore*). 

Berikut adalah panduan lengkap cara menggunakannya melalui **cURL** dan **Python**.

---

## 1. Cek Informasi Database (Snapshot Info)
Mendapatkan statistik ukuran database dan jumlah baris pada setiap tabel.

**Endpoint:** `GET /snapshots/info`

### Contoh cURL
```bash
curl -X GET "http://localhost:8000/snapshots/info"
```

### Contoh Python (Requests)
```python
import requests

response = requests.get("http://localhost:8000/snapshots/info")
if response.status_code == 200:
    print("Database Info:", response.json())
```

---

## 2. Melakukan Backup / Ekspor (Export Snapshot)
Mengunduh seluruh database aplikasi. Kamu bisa memilih format `zip` (file `.db` asli di-*zip* beserta manifest) atau `json` (teks murni yang berisi semua data tabel).

**Endpoint:** `GET /snapshots/export?format={zip|json}`

### Contoh cURL (Download sebagai ZIP)
Menyimpan file backup ke komputer kamu dengan nama `backup_novel.zip`:
```bash
curl -X GET "http://localhost:8000/snapshots/export?format=zip" \
     -o backup_novel.zip
```

### Contoh Python (Download sebagai JSON)
```python
import requests

url = "http://localhost:8000/snapshots/export"
params = {"format": "json"}

response = requests.get(url, params=params, stream=True)
if response.status_code == 200:
    with open("backup_novel.json", "wb") as f:
        for chunk in response.iter_content(chunk_size=8192):
            f.write(chunk)
    print("Backup JSON berhasil disimpan ke 'backup_novel.json'!")
```

---

## 3. Melakukan Pemulihan / Impor (Restore Snapshot)
Mengembalikan data aplikasi ke kondisi saat *backup* dibuat. **Peringatan:** Ini akan menimpa (menggantikan) database kamu yang sekarang!

**Endpoint:** `POST /snapshots/restore`  
*Catatan: Harus menggunakan `multipart/form-data` untuk mengirim file.*

### Contoh cURL (Upload ZIP atau JSON)
Pastikan kamu berada di direktori yang sama dengan file `backup_novel.zip`.
```bash
curl -X POST "http://localhost:8000/snapshots/restore" \
     -H "accept: application/json" \
     -H "Content-Type: multipart/form-data" \
     -F "file=@backup_novel.zip"
```

### Contoh Python (Requests)
```python
import requests

url = "http://localhost:8000/snapshots/restore"
file_path = "backup_novel.zip"

with open(file_path, "rb") as f:
    # Memformat sebagai multipart/form-data
    files = {"file": (file_path, f, "application/zip")}
    response = requests.post(url, files=files)

if response.status_code == 200:
    print("Restore Berhasil:", response.json())
else:
    print("Restore Gagal:", response.text)
```
