# Panduan Manajemen Job & Retry (Mengatasi Kegagalan)

Dokumen ini menjelaskan bagaimana mengelola antrean penerjemahan (Jobs), membersihkan log riwayat yang sudah selesai atau gagal, serta cara mengulang (*retry*) chapter yang gagal dengan mengganti konfigurasi AI Model / API Key secara langsung (*on-the-fly*).

---

## 1. Konsep Dasar: Jobs vs Chapters

Sangat penting untuk dipahami bahwa tabel `jobs` (antrean/riwayat pekerja) **terpisah** dari tabel `chapters` (isi bab yang diterjemahkan). 
- Jika sebuah *Job* dihapus (baik yang berstatus *completed* maupun *failed*), data asli chapter tersebut (teks bahasa asing, status *failed*, dsb) **TIDAK AKAN ikut terhapus**. 
- Data chapter kamu 100% aman dan selalu siap untuk diterjemahkan ulang kapan pun kamu mau.

---

## 2. Membersihkan Log Riwayat (Job Cleanup)

Untuk menjaga database tetap ringan, aplikasi memiliki endpoint untuk menghapus riwayat pekerjaan secara instan.

**Endpoint:** `DELETE /jobs/cleanup`
**Query Parameter:** `status` (opsional, default: `completed`. Nilai yang didukung: `completed`, `failed`)

### Contoh cURL
Menghapus semua job yang sukses dan yang gagal sekaligus:
```bash
curl -X DELETE "http://localhost:8000/jobs/cleanup?status=completed,failed"
```

### Contoh Python (Requests)
```python
import requests

url = "http://localhost:8000/jobs/cleanup"
params = {"status": "completed,failed"}

response = requests.delete(url, params=params)
if response.status_code == 200:
    data = response.json()
    print(f"Berhasil menghapus {data['deleted_count']} jobs.")
else:
    print("Gagal:", response.text)
```

---

## 3. Mengulang (Retry) Chapter yang Gagal

Jika ada chapter yang gagal (misalnya karena API Error, batas waktu habis, dll), Anda dapat meminta *Job Worker* untuk memasukkannya kembali ke antrean menggunakan endpoint `/retranslate`.

**Endpoint:** `POST /series/{series_id}/chapters/{chapter_number}/retranslate`

### Skenario 3A: Retry Biasa (Menggunakan Model Sebelumnya)
Jika kegagalan hanya bersifat sementara (misal: koneksi internet server putus sesaat) dan Anda tidak perlu mengganti model atau API key.

#### Contoh cURL
```bash
curl -X POST "http://localhost:8000/series/1/chapters/25/retranslate"
```

#### Contoh Python (Requests)
```python
import requests

# Mengulang Chapter 25 dari Series 1
url = "http://localhost:8000/series/1/chapters/25/retranslate"

response = requests.post(url)
print("Status Retry:", response.json())
```

---

### Skenario 3B: Retry Sekaligus Ganti/Override Model (Ganti API Key)
Skenario ini digunakan saat:
- Kunci API (*API Key*) yang sebelumnya kamu gunakan sudah limit/habis, dan kamu ingin memasukkan API Key yang baru.
- Kamu ingin pindah dari provider lama (misal: OpenAI) ke provider baru (misal: DeepSeek) secara langsung tanpa harus repot mengatur database.

#### Contoh cURL
```bash
curl -X POST "http://localhost:8000/series/1/chapters/25/retranslate" \
     -H "Content-Type: application/json" \
     -d '{
           "mode": "async",
           "translationModel": {
             "platform": {
               "name": "deepseek",
               "apiKey": "sk-KUNCI_API_DEEPSEEK_YANG_BARU"
             },
             "model": {
               "name": "deepseek-chat"
             }
           }
         }'
```

#### Contoh Python (Requests)
```python
import requests

url = "http://localhost:8000/series/1/chapters/25/retranslate"
payload = {
    "mode": "async",
    "translationModel": {
        "platform": {
            "name": "deepseek",
            "apiKey": "sk-KUNCI_API_DEEPSEEK_YANG_BARU"
        },
        "model": {
            "name": "deepseek-chat"
        }
    }
}

response = requests.post(url, json=payload)
if response.status_code == 200:
    print("Berhasil memasukkan kembali ke antrean dengan model yang baru!")
else:
    print("Error:", response.text)
```

> **Kehebatan Fitur Ini:** 
> Jika platform `deepseek` sudah ada di database, sistem akan menimpa (override) API Key yang lama dengan yang baru. Jika platform `deepseek` belum pernah ada, sistem akan langsung mendaftarkannya (menciptakannya) untukmu secara otomatis. Seluruh antrean yang berada di belakangnya pun akan mengikuti rute API yang baru ini!
