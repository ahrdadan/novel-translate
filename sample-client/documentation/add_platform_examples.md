# Contoh JSON untuk Menambahkan Platform (CLI)

Gunakan contoh JSON di bawah ini saat menambahkan platform baru melalui **Main Menu -> Opsi [3] (Platform & Models List) -> [AP] Add Platform (via JSON)**. 

Setelah Anda menyalin (copy) dan menempel (paste) JSON di CLI, tekan **Enter**, lalu ketik `EOF` (huruf besar) dan tekan **Enter** lagi untuk memprosesnya.

## 1. Menambahkan Satu Platform (Single Object)

Anda dapat menggunakan format object tunggal seperti ini:

```json
{
  "name": "tokenrouter",
  "apiKey": "sk-",
  "apiType": "chat-completions",
  "models": [
    {
      "name": "moonshotai/kimi-k3-free",
      "url": "https://api.tokenrouter.com/v1"
    }
  ]
}
```

*(Catatan: Anda juga bisa menyalin langsung bagian `"platform": { ... }` dari file konfigurasi seperti `series_new_platform_single.json` karena CLI akan otomatis mendeteksi dan menyesuaikan strukturnya).*

## 2. Menambahkan Beberapa Platform Sekaligus (Array)

Jika Anda ingin menambahkan banyak platform sekaligus, gunakan format *array* JSON yang ditandai dengan kurung siku `[ ]`:

```json
[
  {
    "name": "tokenrouter-kimi",
    "apiKey": "sk-KEY_KIMI_ANDA_DISINI",
    "apiType": "chat-completions",
    "models": [
      {
        "name": "moonshotai/kimi-k3-free",
        "url": "https://api.tokenrouter.com/v1"
      }
    ]
  },
  {
    "name": "openai-gpt",
    "apiKey": "sk-KEY_OPENAI_ANDA_DISINI",
    "apiType": "chat-completions",
    "models": [
      {
        "name": "gpt-4o-mini",
        "url": "https://api.openai.com/v1"
      },
      {
        "name": "gpt-3.5-turbo",
        "url": "https://api.openai.com/v1"
      }
    ]
  }
]
```
