import os
import json
import re
import requests
import datetime
import logging
from flask import Flask, request, jsonify, render_template
from flask_caching import Cache
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from flask_swagger_ui import get_swaggerui_blueprint

app = Flask(__name__, static_url_path='/static', static_folder='static')

# Cache config
cache = Cache(app, config={
    "CACHE_TYPE": "SimpleCache",
    "CACHE_DEFAULT_TIMEOUT": 300
})

# Rate limiting
limiter = Limiter(
    get_remote_address,
    app=app,
    default_limits=["200 per day", "50 per hour"],
    storage_uri="memory://"
)

# Swagger
SWAGGER_URL = '/api/docs'
API_URL = '/static/swagger.json'
swaggerui_blueprint = get_swaggerui_blueprint(
    SWAGGER_URL, API_URL, config={"app_name": "GDPR Minimizer API"}
)
app.register_blueprint(swaggerui_blueprint, url_prefix=SWAGGER_URL)

def configure_logging():
    log_level = os.getenv("LOG_LEVEL", "INFO").upper()
    numeric_level = getattr(logging, log_level, logging.INFO)
    app.logger.setLevel(numeric_level)
    formatter = logging.Formatter('[%(asctime)s] %(levelname)s in %(module)s: %(message)s')
    for handler in app.logger.handlers:
        handler.setFormatter(formatter)

def get_llm_endpoint():
    return os.getenv("LLM_BASE_URL", "") + "/chat/completions"

def get_model_name():
    return os.getenv("LLM_MODEL_NAME", "")

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/health')
def health_check():
    return jsonify({
        "status": "healthy",
        "llm_api": "ok" if get_llm_endpoint() else "not_configured",
        "timestamp": datetime.datetime.now().isoformat()
    })

@app.route('/api/minimize', methods=['POST'])
@limiter.limit("10 per minute")
def minimize_api():
    data = request.json
    text = data.get("text", "").strip()
    if not text:
        return jsonify({"error": "Missing 'text' in request"}), 400
    try:
        result = call_llm_minimizer(text)
        return jsonify(result)
    except Exception as e:
        app.logger.error(f"Minimization failed: {e}")
        return jsonify({"error": "Failed to process text"}), 500

@cache.memoize(timeout=300)
def call_llm_minimizer(text):
    system_prompt = """
You are a redaction tool.

You will be given input text. Your job is to identify and redact personal identifiable information (PII), such as names, emails, phone numbers, and addresses.

IMPORTANT:
- Do NOT add or infer any information.
- Do NOT invent content.
- Only redact what is actually present in the input.

Your response must be valid JSON, wrapped inside a triple backtick code block.

Format:

```json
{
  "redacted_text": "the input text with any PII replaced by [TAG]",
  "pii_found": ["PII_TYPE_1", "PII_TYPE_2"]
}
```
If no PII is found, return the original text in redacted_text and an empty list for "pii_found".

Example input: Hi, I'm Clara. You can reach me at clara@email.com.

Expected output:
```json
{
  "redacted_text": "Hi, I'm [NAME]. You can reach me at [EMAIL].",
  "pii_found": ["NAME", "EMAIL"]
}
```
""".strip()
    chat_request = {
    "model": get_model_name(),
    "messages": [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": text}
    ]
}

    headers = {"Content-Type": "application/json"}
    response = requests.post(
        get_llm_endpoint(),
        headers=headers,
        json=chat_request,
        timeout=30
    )

    if response.status_code != 200:
        raise Exception(f"LLM API error: {response.status_code} - {response.text}")

    message = response.json().get("choices", [{}])[0].get("message", {}).get("content", "").strip()

    # Try to extract JSON from a markdown ```json block
    match = re.search(r'```(?:json)?\s*(\{[\s\S]*?\})\s*```', message)
    if match:
        raw_json = match.group(1).strip()
    else:
        try:
            json.loads(message)
            raw_json = message
        except Exception:
            raise ValueError(f"Failed to parse LLM JSON response: {message}")


    try:
        result = json.loads(raw_json)
        if not isinstance(result, dict):
            raise ValueError(f"LLM response is not a JSON object: {raw_json}")

        if "redacted_text" not in result or "pii_found" not in result:
            raise ValueError(f"Missing required fields in LLM response: {raw_json}")

        return {
            "redacted_text": result["redacted_text"],
            "pii_found": result["pii_found"]
        }
    except Exception as e:
        raise ValueError(f"Failed to parse LLM JSON response: {raw_json}") from e



if __name__ == '__main__':
    configure_logging()
    port = int(os.getenv("PORT", 8080))
    app.logger.info(f"Starting GDPR Minimizer on http://0.0.0.0:{port}")
    app.run(host='0.0.0.0', port=port, debug=os.getenv("DEBUG", "false").lower() == "true")
