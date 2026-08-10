# API Requests & URL Samples

This document provides complete, practical code examples and sample URL requests for all endpoints of the **Novel Translation API**. Examples are provided in **cURL**, **HTTP raw format**, **Python (`httpx`)**, and **JavaScript (`fetch`)**.

---

## 📌 Base URL & Headers

Default Local Development Base URL:
```text
http://localhost:8000/api/v1
```

Common HTTP Headers:
```http
Content-Type: application/json
Accept: application/json
```

---

## 🛠️ 1. Global Settings API

### 1.1 Get Global Settings
- **Method**: `GET`
- **URL**: `http://localhost:8000/api/v1/settings`

#### cURL
```bash
curl -X GET "http://localhost:8000/api/v1/settings" \
     -H "Accept: application/json"
```

#### HTTP Raw
```http
GET /api/v1/settings HTTP/1.1
Host: localhost:8000
Accept: application/json
```

#### Python
```python
import httpx

response = httpx.get("http://localhost:8000/api/v1/settings")
print(response.json())
```

---

### 1.2 Update Settings
- **Method**: `PATCH`
- **URL**: `http://localhost:8000/api/v1/settings`

#### Request Payload
```json
{
  "max_concurrent_jobs": 5,
  "default_translation_model_id": 1,
  "default_extraction_model_id": 2,
  "default_system_prompt_id": 1
}
```

#### cURL
```bash
curl -X PATCH "http://localhost:8000/api/v1/settings" \
     -H "Content-Type: application/json" \
     -d '{
           "max_concurrent_jobs": 5,
           "default_translation_model_id": 1,
           "default_extraction_model_id": 2,
           "default_system_prompt_id": 1
         }'
```

---

## 📝 2. System Prompts API

### 2.1 List All System Prompts
- **Method**: `GET`
- **URL**: `http://localhost:8000/api/v1/system-prompts`

#### cURL
```bash
curl -X GET "http://localhost:8000/api/v1/system-prompts"
```

---

### 2.2 Create a New Custom System Prompt
- **Method**: `POST`
- **URL**: `http://localhost:8000/api/v1/system-prompts`

#### Request Payload
```json
{
  "name": "wuxia-style",
  "prompt_text": "You are an expert translator specializing in Xianxia and Wuxia web novels. Maintain dramatic tension, martial arts technique names, and ancient formal registers.",
  "is_default": false
}
```

#### cURL
```bash
curl -X POST "http://localhost:8000/api/v1/system-prompts" \
     -H "Content-Type: application/json" \
     -d '{
           "name": "wuxia-style",
           "prompt_text": "You are an expert translator specializing in Xianxia and Wuxia web novels. Maintain dramatic tension, martial arts technique names, and ancient formal registers.",
           "is_default": false
         }'
```

---

### 2.3 Update a System Prompt
- **Method**: `PATCH`
- **URL**: `http://localhost:8000/api/v1/system-prompts/2`

#### Request Payload
```json
{
  "prompt_text": "Updated custom prompt text for Xianxia novels with enhanced tone instructions."
}
```

#### cURL
```bash
curl -X PATCH "http://localhost:8000/api/v1/system-prompts/2" \
     -H "Content-Type: application/json" \
     -d '{
           "prompt_text": "Updated custom prompt text for Xianxia novels with enhanced tone instructions."
         }'
```

---

### 2.4 Set Prompt as Global Default
- **Method**: `POST`
- **URL**: `http://localhost:8000/api/v1/system-prompts/2/set-default`

#### cURL
```bash
curl -X POST "http://localhost:8000/api/v1/system-prompts/2/set-default"
```

---

## 🌐 3. Platform & Model Management API

### 3.1 Add a Platform (with optional initial models)
- **Method**: `POST`
- **URL**: `http://localhost:8000/api/v1/platforms`

#### Option A: Add Platform Only
##### Request Payload
```json
{
  "name": "aihubmix",
  "api_key": "sk-aihubmix-secret-key-12345",
  "api_type": "chat-completions"
}
```

##### cURL
```bash
curl -X POST "http://localhost:8000/api/v1/platforms" \
     -H "Content-Type: application/json" \
     -d '{
           "name": "aihubmix",
           "api_key": "sk-aihubmix-secret-key-12345",
           "api_type": "chat-completions"
         }'
```

#### Option B: Add Platform and Models Simultaneously
##### Request Payload
```json
{
  "name": "aihubmix",
  "api_key": "sk-aihubmix-secret-key-12345",
  "api_type": "chat-completions",
  "models": [
    {
      "name": "gpt-4o",
      "url": "https://aihubmix.com/v1"
    },
    {
      "name": "claude-3-5-sonnet",
      "url": "https://aihubmix.com/v1"
    }
  ]
}
```

##### cURL
```bash
curl -X POST "http://localhost:8000/api/v1/platforms" \
     -H "Content-Type: application/json" \
     -d '{
           "name": "aihubmix",
           "api_key": "sk-aihubmix-secret-key-12345",
           "api_type": "chat-completions",
           "models": [
             {
               "name": "gpt-4o",
               "url": "https://aihubmix.com/v1"
             },
             {
               "name": "claude-3-5-sonnet",
               "url": "https://aihubmix.com/v1"
             }
           ]
         }'
```


---

### 3.2 Add Model to Platform
- **Method**: `POST`
- **URL**: `http://localhost:8000/api/v1/platforms/1/models`

#### Request Payload
```json
{
  "name": "gpt-5.5-free",
  "url": "https://aihubmix.com"
}
```

#### cURL
```bash
curl -X POST "http://localhost:8000/api/v1/platforms/1/models" \
     -H "Content-Type: application/json" \
     -d '{
           "name": "gpt-5.5-free",
           "url": "https://aihubmix.com"
         }'
```

---

## 📚 4. Series & Chapter Management API

### 4.1 Create a Novel Series (with custom system prompt ID)
- **Method**: `POST`
- **URL**: `http://localhost:8000/api/v1/series`

#### Request Payload
```json
{
  "name": "Shadow Slave",
  "original_title": "Shadow Slave Original",
  "author": "Guiltythree",
  "description": "Growing up in poverty, Sunny never expected anything good from life.",
  "status": "ongoing",
  "translation_model_id": 1,
  "system_prompt_id": 2
}
```

#### cURL
```bash
curl -X POST "http://localhost:8000/api/v1/series" \
     -H "Content-Type: application/json" \
     -d '{
           "name": "Shadow Slave",
           "original_title": "Shadow Slave Original",
           "author": "Guiltythree",
           "description": "Growing up in poverty, Sunny never expected anything good from life.",
           "status": "ongoing",
           "translation_model_id": 1,
           "system_prompt_id": 2
         }'
```

---

## ⚡ 5. Translation & Async Jobs API

### 5.1 Trigger Chapter Translation (with Custom System Prompt Reference)
- **Method**: `POST`
- **URL**: `http://localhost:8000/api/v1/series/1/chapters/1/translate`

#### Request Payload (with System Prompt ID or Inline Prompt)
```json
{
  "mode": "async",
  "force_translate": false,
  "extract": true,
  "system_prompt": {
    "system_prompt_id": 2
  },
  "translation_model": {
    "platform": {
      "name": "aihubmix",
      "apiType": "chat-completions",
      "apiKey": "sk-aihubmix-secret-key"
    },
    "model": {
      "name": "gpt-5.5-free",
      "url": "https://aihubmix.com"
    }
  }
}
```

#### cURL
```bash
curl -X POST "http://localhost:8000/api/v1/series/1/chapters/1/translate" \
     -H "Content-Type: application/json" \
     -d '{
           "mode": "async",
           "force_translate": false,
           "extract": true,
           "system_prompt": {
             "system_prompt_id": 2
           },
           "translation_model": {
             "platform": {
               "name": "aihubmix",
               "apiType": "chat-completions",
               "apiKey": "sk-aihubmix-secret-key"
             },
             "model": {
               "name": "gpt-5.5-free",
               "url": "https://aihubmix.com"
             }
           }
         }'
```

---

### 5.2 Poll Async Job Status
- **Method**: `GET`
- **URL**: `http://localhost:8000/api/v1/jobs/42`

#### cURL
```bash
curl -X GET "http://localhost:8000/api/v1/jobs/42"
```

---

### 5.3 JavaScript Fetch Example (Custom System Prompt + Translation)
```javascript
async function translateWithCustomPrompt(seriesId, chapterNum, promptId) {
  const response = await fetch(`http://localhost:8000/api/v1/series/${seriesId}/chapters/${chapterNum}/translate`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      mode: 'async',
      system_prompt: {
        system_prompt_id: promptId
      }
    })
  });
  
  const job = await response.json();
  console.log(`Job queued: ${job.job_id}`);
  return job;
}
```

---

## 🚀 6. Unified All-In-One Translation API (`POST /api/v1/translate-novel`)

This endpoint creates/resolves Series, Chapter (with automatic HTML cleaning), Platform, Model, and triggers Translation in a single API request.

---

### 📋 6.1 Complete Endpoint Parameter Specification Table

| Parameter / Field | Type | Status | Default | Description & Resolution Rule |
|---|---|---|---|---|
| **`series`** | `Object` \| `Integer` \| `String` | **Required** | — | **Series Reference**: Can be object `{"name": "..."}`, ID integer `1`, or string `"Shadow Slave"`. Resolved by ID or Name if existing; created automatically if Name is not found. |
| `series.id` | `Integer` | *Optional* | `null` | Existing Series ID in database. |
| `series.name` | `String` | *Optional* | `null` | Series title. If series already exists, resolved by Name. If missing, creates a new series. |
| `series.author` | `String` | *Optional* | `null` | Author name (used only when creating a new series). |
| `series.description` | `String` | *Optional* | `null` | Series synopsis (used only when creating a new series). |
| **`chapter`** | `Object` \| `Integer` | **Required** | — | **Chapter Input**: Can be object or integer chapter number `1`. |
| `chapter.chapterNumber` | `Integer` | **Required** | — | Chapter sequence number (e.g., `1`, `2`). |
| `chapter.title` | `String` | *Optional* | `null` | Chapter title. |
| `chapter.sourceText` | `String` | **Required*** | `null` | Raw text or HTML string. **Required for new chapters**. *Optional if chapter already exists in DB*. |
| `chapter.sourceLanguage` | `String` | *Optional* | `"auto"` | Source language code (`"auto"`, `"zh"`, `"ja"`, `"ko"`). |
| **`translationModel`** | `Object` \| `Integer` | *Optional* | `null` | **Translation Model Reference**: Can be integer ID `2`, or platform object. |
| `translationModel.modelId` | `Integer` | *Optional* | `null` | Direct model ID from database. |
| `translationModel.platform` | `Object` | *Optional* | `null` | Platform object containing `name` or `id`, and single `model` or `models` array. |
| `translationModel.platform.id` | `Integer` | *Optional* | `null` | Existing Platform ID. |
| `translationModel.platform.name` | `String` | *Optional* | `null` | Platform provider name (e.g., `"aihubmix"`). Resolves existing or creates new. |
| `translationModel.platform.apiKey` | `String` | *Optional* | `null` | API key credential for provider. |
| `translationModel.platform.apiType` | `String` | *Optional* | `"chat-completions"` | API protocol format (`"chat-completions"`, `"responses"`, `"messages"`). |
| `translationModel.platform.model` | `Object` | *Optional* | `null` | **Single Model Object (1 Chapter 1 Model)**: `{"name": "gpt-4o", "url": "..."}`. |
| `translationModel.platform.models` | `Array` | *Optional* | `null` | **Multiple Models Array**: `[{"name": "gpt-4o"}, {"name": "claude-3-5-sonnet"}]`. |
| **`extractionModel`** | `Object` \| `Integer` | *Optional* | `null` | Extraction Model Reference (same structure as `translationModel`). |
| **`systemPrompt`** | `Object` \| `Integer` | *Optional* | `null` | Custom System Prompt: `{"system_prompt_id": 2}` or `{"prompt_text": "..."}`. |
| **`mode`** | `String` | *Optional* | `"sync"` | Execution mode: `"sync"` (blocking response) or `"async"` (job queue polling). |
| **`forceTranslate`** | `Boolean` | *Optional* | `false` | Set `true` to force re-translating an already translated chapter. |
| **`forceSummary`** | `Boolean` | *Optional* | `false` | Set `true` to force re-generating chapter plot summary. |
| **`extract`** | `Boolean` | *Optional* | `true` | Set `true` to auto-extract newly introduced characters and glossary terms. |

---

### 💡 6.2 Scenario 1: Existing Series + New Chapter + Existing Platform & Model
Use existing Series by Name (no need to resend author/description) and existing Platform/Model:

```json
{
  "series": {
    "name": "Shadow Slave"
  },
  "chapter": {
    "chapterNumber": 2,
    "title": "Chapter 2: The First Nightmare",
    "sourceText": "<div><h1>Chapter 2</h1><p>Sunny opened his eyes in the temple.</p></div>"
  },
  "translationModel": {
    "platform": {
      "name": "aihubmix",
      "model": {
        "name": "gpt-4o"
      }
    }
  },
  "mode": "sync",
  "extract": true
}
```

#### cURL
```bash
curl -X POST "http://localhost:8000/api/v1/translate-novel" \
     -H "Content-Type: application/json" \
     -d '{
           "series": {
             "name": "Shadow Slave"
           },
           "chapter": {
             "chapterNumber": 2,
             "title": "Chapter 2: The First Nightmare",
             "sourceText": "<div><h1>Chapter 2</h1><p>Sunny opened his eyes in the temple.</p></div>"
           },
           "translationModel": {
             "platform": {
               "name": "aihubmix",
               "model": {
                 "name": "gpt-4o"
               }
             }
           },
           "mode": "sync",
           "extract": true
         }'
```

---

### 💡 6.3 Scenario 2: Brand New Everything (New Series + HTML Chapter + New Platform & Model)
Creates a new Series, parses/cleans raw HTML chapter text, registers new Platform & Model credentials, and translates:

```json
{
  "series": {
    "name": "Lord of the Mysteries",
    "author": "Cuttlefish That Loves Diving",
    "description": "With the rising tide of steam and machinery..."
  },
  "chapter": {
    "chapterNumber": 1,
    "title": "Chapter 1: Crimson",
    "sourceText": "<div><h1>Chapter 1</h1><p>Pain. Painful. Painful in the head.</p></div>"
  },
  "translationModel": {
    "platform": {
      "name": "aihubmix",
      "apiKey": "sk-aihubmix-secret-key-12345",
      "apiType": "chat-completions",
      "model": {
        "name": "gpt-4o",
        "url": "https://aihubmix.com/v1"
      }
    }
  },
  "mode": "sync",
  "extract": true
}
```

#### cURL
```bash
curl -X POST "http://localhost:8000/api/v1/translate-novel" \
     -H "Content-Type: application/json" \
     -d '{
           "series": {
             "name": "Lord of the Mysteries",
             "author": "Cuttlefish That Loves Diving"
           },
           "chapter": {
             "chapterNumber": 1,
             "title": "Chapter 1: Crimson",
             "sourceText": "<div><h1>Chapter 1</h1><p>Pain. Painful.</p></div>"
           },
           "translationModel": {
             "platform": {
               "name": "aihubmix",
               "apiKey": "sk-aihubmix-secret-key-12345",
               "apiType": "chat-completions",
               "model": {
                 "name": "gpt-4o",
                 "url": "https://aihubmix.com/v1"
               }
             }
           },
           "mode": "sync",
           "extract": true
         }'
```

---

### 💡 6.4 Scenario 3: Add New Model to Existing Platform
Registers a new model (`claude-3-5-sonnet`) under an existing platform (`aihubmix`) and uses it for this chapter:

```json
{
  "series": { "name": "Shadow Slave" },
  "chapter": {
    "chapterNumber": 3,
    "sourceText": "<p>Chapter 3 text...</p>"
  },
  "translationModel": {
    "platform": {
      "name": "aihubmix",
      "model": {
        "name": "claude-3-5-sonnet",
        "url": "https://aihubmix.com/v1"
      }
    }
  },
  "mode": "sync"
}
```

---

### 💡 6.5 Scenario 4: Re-Translate Existing Chapter using Text from Database & Direct Model ID
Re-translates an existing chapter in database by integer IDs without re-sending chapter text or platform credentials:

```json
{
  "series": 1,
  "chapter": 1,
  "translationModel": 2,
  "mode": "async",
  "forceTranslate": true
}
```

#### cURL
```bash
curl -X POST "http://localhost:8000/api/v1/translate-novel" \
     -H "Content-Type: application/json" \
     -d '{
           "series": 1,
           "chapter": 1,
           "translationModel": 2,
           "mode": "async",
           "forceTranslate": true
         }'
```




