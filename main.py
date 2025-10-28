import os
from flask import Flask, request, jsonify
from google.cloud import storage, secretmanager
import google.generativeai as genai

app = Flask(__name__)

# --- Secret Managerから値を取得する関数 ---
def get_secret(secret_id: str) -> str:
    client = secretmanager.SecretManagerServiceClient()
    project_id = os.environ.get("GOOGLE_CLOUD_PROJECT", "horse-nft-lab-clean")
    name = f"projects/{project_id}/secrets/{secret_id}/versions/latest"
    response = client.access_secret_version(request={"name": name})
    return response.payload.data.decode("utf-8")

# --- Secrets の読み込み ---
GEMINI_API_KEY = get_secret("GEMINI_API_KEY")
GCS_BUCKET = get_secret("GCS_BUCKET")

# --- クライアント初期化 ---
genai.configure(api_key=GEMINI_API_KEY)
storage_client = storage.Client()

@app.route("/")
def index():
    return "✅ Flask app is running safely without blockchain components."

@app.route("/upload", methods=["POST"])
def upload_file():
    """ファイルをGCSにアップロードするAPI"""
    file = request.files.get("file")
    if not file:
        return jsonify({"error": "No file provided"}), 400

    bucket = storage_client.bucket(GCS_BUCKET)
    blob = bucket.blob(file.filename)
    blob.upload_from_file(file)
    return jsonify({"message": f"File {file.filename} uploaded successfully to {GCS_BUCKET}"}), 200

@app.route("/generate", methods=["POST"])
def generate_text():
    """Gemini APIでテキスト生成"""
    data = request.json
    prompt = data.get("prompt", "")
    if not prompt:
        return jsonify({"error": "No prompt provided"}), 400

    model = genai.GenerativeModel("gemini-1.5-flash")
    response = model.generate_content(prompt)
    return jsonify({"response": response.text}), 200

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 8080)))
