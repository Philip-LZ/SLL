import requests
import json

url = "https://api.bochaai.com/v1/web-search"

payload = json.dumps({
  "query": "天空为什么是蓝色的？",
  "summary": True,
  "count": 10,
  "page": 1
})

headers = {
  'Authorization': 'Bearer sk-8b820243c782484e99c192ebf9c843f2',
  'Content-Type': 'application/json'
}

response = requests.request("POST", url, headers=headers, data=payload)

print(response.json())