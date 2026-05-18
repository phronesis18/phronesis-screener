import requests

# Remplace par ta vraie clé API DeepSeek
API_KEY = "sk-8a81b007a68840eb8d59027d62d13c4a"

headers = {
    "Authorization": f"Bearer {API_KEY}",
    "Content-Type": "application/json"
}

data = {
    "model": "deepseek-chat",
    "messages": [
        {"role": "user", "content": "Dis bonjour en français"}
    ],
    "max_tokens": 20
}

response = requests.post(
    "https://api.deepseek.com/chat/completions",
    headers=headers,
    json=data
)

print("Status code:", response.status_code)
print("Response:", response.text)