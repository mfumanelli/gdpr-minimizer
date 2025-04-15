# gdpr-data-minimizer

This is a privacy-first API that uses a local LLM (like Mistral) to detect and redact personal identifiable information such as names, emails, phone numbers, and addresses from unstructured text.

Built for GDPR compliance, data minimization, and secure AI-powered processing.

---

## How to Run

### 1. Clone the project

```bash
git clone https://github.com/mfumanelli/gdpr-minimizer.git
cd gdpr-data-minimizer
```

### 2. Set environment variables (optional)
Update the .env file with your model:
```bash
LLM_MODEL_NAME=ai/mistral-7b-instruct.Q6_K
```

### 3. Run the app
```bash
./run.sh
```

Once running, open:
* 👉 http://localhost:8080
* 👉 Swagger docs: http://localhost:8080/api/docs
