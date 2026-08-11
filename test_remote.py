import urllib.request
import urllib.error
import json

data = {
    'series': 'test2',
    'chapter': {'chapterNumber': 1, 'sourceText': '<p>test</p>'},
    'mode': 'async',
    'translationModel': [
        {
            'platform': {'name': 'test_plat1'},
            'model': {'name': 'test_model1'}
        },
        {
            'platform': {'name': 'test_plat2'},
            'model': {'name': 'test_model2'}
        }
    ]
}

req = urllib.request.Request(
    'http://127.0.0.1:8000/api/v1/translate-novel',
    data=json.dumps(data).encode(),
    headers={'Content-Type': 'application/json'}
)

try:
    resp = urllib.request.urlopen(req)
    print("SUCCESS:", resp.read().decode())
except urllib.error.HTTPError as e:
    print("HTTP Error:", e.code)
    print(e.read().decode())
except Exception as e:
    print("Other error:", e)
