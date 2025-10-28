import os
import uuid
import io
import json
import re
import sys, traceback
from flask import Flask, render_template_string, request
import google.generativeai as genai
from google.cloud import storage, secretmanager

app = Flask(__name__)

# --- Secret Managerから値を取得 ---
def get_secret(secret_id: str) -> str:
    client = secretmanager.SecretManagerServiceClient()
    project_id = os.environ.get("GOOGLE_CLOUD_PROJECT", "horse-nft-lab-clean")
    name = f"projects/{project_id}/secrets/{secret_id}/versions/latest"
    response = client.access_secret_version(request={"name": name})
    return response.payload.data.decode("utf-8")

# --- Secrets 読み込み ---
GCS_BUCKET = get_secret("GCS_BUCKET")
GEMINI_API_KEY = get_secret("GEMINI_API_KEY")

genai.configure(api_key=GEMINI_API_KEY)
storage_client = storage.Client()

PROJECT = os.environ.get("GOOGLE_CLOUD_PROJECT", "horse-nft-lab-clean")

# --- SLIログ出力 ---
def log_sli(event_name: str, success: bool):
    severity = "INFO" if success else "ERROR"
    entry = {
        "severity": severity,
        "sli_event": event_name,
        "success": success,
        "component": "sli"
    }
    trace_header = request.headers.get("X-Cloud-Trace-Context")
    if trace_header:
        trace = trace_header.split("/")
        entry["logging.googleapis.com/trace"] = f"projects/{PROJECT}/traces/{trace[0]}"
    sys.stdout.write(json.dumps(entry) + "\n")

# --- 星評価変換 ---
def stars(score):
    try:
        score = int(score)
        level = max(1, min(5, round(score / 20)))
    except:
        level = 1
    return "★" * level + "☆" * (5 - level)

# --- HTML部分（省略なし） ---
HTML_FORM = """（中略：元の診断フォームHTMLをそのまま貼る）"""
RESULT_HTML = """（中略：元の結果表示HTMLをそのまま貼る）"""

@app.route("/")
def index():
    return render_template_string(HTML_FORM)

@app.route("/generate", methods=["POST"])
def generate():
    try:
        traits = request.form.getlist("traits")
        model = genai.GenerativeModel("gemini-2.5-flash")

        prompt_json = f"""
性格タイプ {traits} に基づいて、以下形式のJSONを出力してください。
余分な説明文は不要です。JSONのみを返してください。馬名はカタカナで競走馬っぽく。

{{
  "name": "馬名",
  "type": "脚質（逃げ・先行・差し・追込）",
  "stats": {{
    "スピード": 数値,
    "スタミナ": 数値,
    "パワー": 数値,
    "敏捷性": 数値
  }}
}}
        """

        response = model.generate_content(prompt_json)
        raw_text = getattr(response, "text", "") or getattr(response.candidates[0].content.parts[0], "text", "")

        match = re.search(r'\{.*\}', raw_text, re.DOTALL)
        if not match:
            raise ValueError("Geminiが有効なJSONを返しませんでした。")

        data = json.loads(match.group(0))
        name = data.get("name", "Unknown Horse")
        type_ = data.get("type", "不明")
        stats = data.get("stats", {})
        stats_star = {k: stars(v) for k, v in stats.items()}

        # --- 画像生成 ---
        image_prompt = f"A realistic racehorse named {name}, running alone on a Japanese race track, {type_} style, no humans, realistic lighting, dirt flying."
        image_model = genai.GenerativeModel("gemini-2.5-flash-image")

        image_data = None
        for attempt in range(3):
            try:
                img_response = image_model.generate_content(image_prompt)
                if hasattr(img_response, "candidates"):
                    for part in img_response.candidates[0].content.parts:
                        if getattr(part, "inline_data", None):
                            image_data = part.inline_data.data
                            break
                if image_data:
                    break
            except Exception as e:
                print(f"⚠️ Image retry {attempt+1}/3 failed: {e}", file=sys.stderr)

        if not image_data:
            image_url = "/static/fallback_horse.png"
        else:
            bucket = storage_client.bucket(GCS_BUCKET)
            filename = f"output/horse_{uuid.uuid4().hex[:6]}.png"
            blob = bucket.blob(filename)
            blob.upload_from_string(image_data, content_type="image/png")
            image_url = blob.public_url

        log_sli("horse_generate", True)
        return render_template_string(RESULT_HTML, name=name, type=type_, stats=stats_star, image_url=image_url)

    except Exception:
        log_sli("horse_generate", False)
        print(traceback.format_exc(), file=sys.stderr)
        return "Internal Server Error", 500

@app.route("/debug-sli")
def debug_sli():
    log_sli("horse_generate", True)
    return "SLI logged", 200

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 8080)))
