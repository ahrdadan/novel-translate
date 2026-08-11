# Cara Mengatasi dan Melanjutkan Sistem Setelah Quota API Habis

Jika *Circuit Breaker* aktif karena API key kehabisan saldo/token (status 401/403/429), status global aplikasi akan menjadi **Paused** (`is_paused = 1`), dan antrean akan membeku. Job-job sebelumnya yang diproses saat saldo habis akan memiliki status `failed`.

Berikut adalah langkah-langkah dan contoh request API untuk memperbaiki API key (override) dan melanjutkan kembali (resume) antrean, serta mengulang (retry) job yang gagal.

---

## Langkah 1: Update API Key (Melalui Retry salah satu Job)

Berkat fitur *Create-or-Append Logic* pada `model_resolver`, kamu tidak perlu mengedit database secara manual. Kamu cukup melakukan **Retry (`/retranslate`) pada salah satu chapter yang gagal**, sambil menyisipkan objek `translationModel` dengan nama *platform* yang sama tetapi dengan `apiKey` yang **baru**.

Sistem akan mendeteksi bahwa nama platform tersebut sudah ada di database, lalu **otomatis mengupdate/menimpa (override) API Key lama dengan yang baru**.

### Contoh Request (cURL)
Misalnya kita mengulang Chapter 25 dari Series ID 1:

```bash
curl -X POST "http://localhost:8000/series/1/chapters/25/retranslate" \
     -H "Content-Type: application/json" \
     -d '{
           "mode": "async",
           "translationModel": {
             "platform": {
               "name": "tokenrouter",
               "apiKey": "sk-NEW_API_KEY_YANG_BERISI_SALDO"
             },
             "model": {
               "name": "moonshotai/kimi-k3-free"
             }
           }
         }'
```
> **Catatan:** Setelah request di atas dieksekusi, API key untuk platform `"tokenrouter"` di dalam database akan ter-update menjadi kunci yang baru.

---

## Langkah 2: Buka Penahan Antrean (Unpause / Resume Job Worker)

Setelah kunci API diperbarui, kamu perlu "membangunkan" *Job Worker* dengan mengubah pengaturan global `is_paused` menjadi `false`.

### Contoh Request (cURL)

```bash
curl -X PATCH "http://localhost:8000/settings" \
     -H "Content-Type: application/json" \
     -d '{
           "is_paused": false
         }'
```

Begitu status `is_paused` menjadi `false`, *Job Worker* akan otomatis terbangun, membaca antrean dari database, dan langsung mengeksekusi sisa chapter (Chapter 26 dan seterusnya) yang masih berstatus `queued`. Karena API key pada platform sudah di-*override* di Langkah 1, sisa antrean ini akan menggunakan API key yang baru.

---

## Langkah 3: Retry Sisa Job yang `failed` (Opsional)

Jika ada beberapa chapter yang terlanjur menjadi `failed` sebelum *Circuit Breaker* aktif (misal Chapter 23 dan 24), kamu cukup melakukan `/retranslate` atau menekan tombol Retry pada UI untuk chapter-chapter tersebut tanpa perlu mengirim ulang payload `translationModel`. 

```bash
curl -X POST "http://localhost:8000/series/1/chapters/23/retranslate"
```

Otomatis mereka akan terbaca ulang dan masuk ke antrean menggunakan konfigurasi/API Key dari platform yang baru saja kita *update*.
