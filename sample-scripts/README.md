# 📖 Novel Translation Client Runner & CLI (`sample-scripts/`)

Aplikasi client standalone untuk membaca file konfigurasi `.json`, folder HTML, serta metadata **`toc.json` (Table of Contents)** untuk mengirimkan chapter novel ke API **Novel Translation System**.

---

## 📁 Struktur Folder `sample-scripts/`

```text
sample-scripts/
├── main.py                     # Skrip utama CLI Runner & Batch TOC Parser
├── series.json                 # Config batch multi-chapter (Model ID Terdaftar)
├── series_new_platform.json    # Config batch multi-chapter (Platform & Model Baru Inline)
├── series_single_chapter.json  # Config 1 file HTML chapter
├── generate-toc.py             # Script otomatis pembuat toc.json dari file HTML
├── README.md                   # Panduan dokumentasi
└── novel-html/                 # Folder chapter HTML & TOC Metadata
    ├── toc.json                # Metadata daftar chapter, nomor, judul, dan filename HTML
    ├── response_chapter0006.html
    ├── response_chapter0007.html
    ├── response_chapter0008.html
    ├── response_chapter0009.html
    └── response_chapter0010.html
```

---

## 🛠️ Auto-Generate `toc.json` (`generate-toc.py`)

Jika Anda memiliki banyak file HTML dan tidak ingin membuat `toc.json` secara manual, Anda bisa menggunakan script `generate-toc.py`. Script ini akan otomatis membaca urutan file HTML, mengambil judul dari tag `<h1>`, dan mengenerate file `toc.json` yang siap digunakan.

**Cara Penggunaan:**
```bash
# Menjalankan dengan folder target novel-html dan mulai dari chapter 1
python sample-scripts/generate-toc.py -d novel-html -s 1
```

- `-d` atau `--dir` : Menentukan nama atau path folder tempat file HTML berada (default: `novel-html`).
- `-s` atau `--start` : Menentukan angka untuk mulai menghitung `chapterNumber` (default: 1).

---

## 📄 Format Metadata `novel-html/toc.json`

File `toc.json` diletakkan di dalam folder `novel-html/` untuk mendefinisikan nomor chapter, judul, dan nama file HTML:

```json
[
  {
    "chapterNumber": 6,
    "title": "Lee Ha-young - Part 1",
    "file": "response_chapter0006.html"
  },
  {
    "chapterNumber": 7,
    "title": "Lee Ha-young - Part 2",
    "file": "response_chapter0007.html"
  },
  {
    "chapterNumber": 8,
    "title": "Lee Ha-young - Part 3",
    "file": "response_chapter0008.html"
  },
  {
    "chapterNumber": 9,
    "title": "Lee Ha-young - Part 4",
    "file": "response_chapter0009.html"
  },
  {
    "chapterNumber": 10,
    "title": "Lee Ha-young - Part 5",
    "file": "response_chapter0010.html"
  }
]
```

---

## ⚙️ Format Konfigurasi JSON (`series_new_platform.json`)

```json
{
  "series": {
    "name": "Lee Ha-young (New Platform Demo)",
    "originalTitle": "이하영",
    "author": "Web Novel Author",
    "description": "Multi-chapter HTML novel dengan TOC metadata dan Platform/Model baru inline",
    "sourceLanguage": "Korean",
    "targetLanguage": "Indonesian"
  },
  "chaptersFolder": "novel-html",
  "translationModel": {
    "platform": {
      "name": "aihubmix-custom-provider",
      "apiKey": "sk-aihubmix-secret-key-12345",
      "apiType": "chat-completions",
      "models": [
        {
          "name": "gpt-4o-mini",
          "url": "https://aihubmix.com/v1"
        }
      ]
    }
  },
  "mode": "async",
  "strategy": "pipeline"
}
```

---

## 🚀 Cara Menjalankan

### Perintah Terminal Direct Execution:
```bash
# Menjalankan multi-chapter dari folder novel-html/ via toc.json dengan Platform & Model Baru Inline:
uv run python sample-scripts/main.py sample-scripts/series_new_platform.json

# Menjalankan multi-chapter dengan Default Model ID:
uv run python sample-scripts/main.py sample-scripts/series.json

# Menjalankan script dengan server yang berbeda (Custom Endpoint URL):
# Berguna jika backend berjalan di IP/Port berbeda atau di Cloud VPS.
uv run python sample-scripts/main.py sample-scripts/series_new_platform.json --base-url http://192.168.1.100:9000
```

**Output Terminal:**
```text
=================================================================
 📖  NOVEL TRANSLATION SYSTEM — CLIENT RUNNER & CLI
=================================================================
 Connected Server Base URL: http://localhost:8000

📂 Membaca Konfigurasi dari: sample-scripts/series_new_platform.json
[OK] Membaca TOC Metadata dari: toc.json
[OK] Ditemukan 5 chapter HTML untuk diproses.

  [1/5] Submitting Chapter 6 (response_chapter0006.html)...
    + Success [200] | Job ID: 24 | Status: queued
  [2/5] Submitting Chapter 7 (response_chapter0007.html)...
    + Success [200] | Job ID: 25 | Status: queued
  [3/5] Submitting Chapter 8 (response_chapter0008.html)...
    + Success [200] | Job ID: 26 | Status: queued
  [4/5] Submitting Chapter 9 (response_chapter0009.html)...
    + Success [200] | Job ID: 27 | Status: queued
  [5/5] Submitting Chapter 10 (response_chapter0010.html)...
    + Success [200] | Job ID: 28 | Status: queued

=================================================================
HASIL BATCH IMPORT: 5/5 Chapter Berhasil Dikirim.
=================================================================
```
