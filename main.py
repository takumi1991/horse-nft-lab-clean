import os
import uuid
import io
from flask import Flask, render_template, render_template_string, request
import google.generativeai as genai  # ←ここを修正！
from PIL import Image, ImageDraw
from google.cloud import storage
from datetime import timedelta
import sys, traceback

app = Flask(__name__)

# --- 環境変数 ---
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
GCS_BUCKET = os.getenv("GCS_BUCKET")
if not GEMINI_API_KEY:
    raise RuntimeError("GEMINI_API_KEY が設定されていません。")
if not GCS_BUCKET:
    raise RuntimeError("GCS_BUCKET が設定されていません。")

# ✅ 新しい初期化方法
genai.configure(api_key=GEMINI_API_KEY)
storage_client = storage.Client()

# --- 星変換 ---
def stars(score):
    try:
        score = int(score)
        level = max(1, min(5, round(score / 20)))
    except:
        level = 1
    return "★" * level + "☆" * (5 - level)

# --- HTML ---
HTML_FORM = """
<!doctype html>
<html lang="ja">
<head><meta charset="utf-8"><title>AI競走馬メーカー</title></head>
<body>
  <h1>🐴 AI競走馬メーカー</h1>
  <form action="/generate" method="post">
    <p>あなたの性格タイプを選んでください：</p>
    <input type="checkbox" name="traits" value="brave">勇敢
    <input type="checkbox" name="traits" value="calm">落ち着き
    <input type="checkbox" name="traits" value="agile">俊敏
    <input type="checkbox" name="traits" value="loyal">忠実
    <input type="checkbox" name="traits" value="clever">賢い
    <p><input type="submit" value="診断開始"></p>
  </form>
</body>
</html>
"""

RESULT_HTML = """
<!doctype html>
<html lang="ja">
<head><meta charset="utf-8"><title>AI競走馬結果</title></head>
<body>
  <h1>🐎 {{name}}</h1>
  <p><b>脚質:</b> {{type}}</p>
  {% if image_url %}
    <img src="{{image_url}}" width="400"><br><br>
  {% else %}
    <p>⚠️ 画像生成に失敗しました。</p>
  {% endif %}
  <h3>能力ステータス</h3>
  <ul>
    {% for k, v in stats.items() %}
      <li><b>{{k}}</b>: {{v}}</li>
    {% endfor %}
  </ul>
  <p><a href="/">もう一度診断する</a></p>
</body>
</html>
"""

@app.route("/")
def index():
    return render_template_string(HTML_FORM)

@app.route("/generate", methods=["POST"])
def generate():
    try:
        traits = request.form.getlist("traits")

        # --- JSON形式で能力を生成 ---
        prompt = f"""
性格タイプ {traits} に基づき、以下のJSON形式で出力してください。
文章は不要です。

{{
  "name": "馬名（意味のある造語や自然モチーフ）",
  "type": "脚質（逃げ・先行・差し・追込）",
  "stats": {{
    "Speed": 0-100,
    "Stamina": 0-100,
    "Power": 0-100,
    "Agility": 0-100,
    "Intelligence": 0-100,
    "Temperament": 0-100,
    "Endurance": 0-100,
    "Charm": 0-100
  }}
}}
        """

        response = client.models.generate_content(
            model="gemini-2.5-flash",
            contents=[prompt]
        )
        raw_text = response.candidates[0].content.parts[0].text
        print("Gemini JSON:", raw_text, file=sys.stderr)
        data = json.loads(raw_text)

        name = data.get("name", "Unknown Horse")
        type_ = data.get("type", "不明")
        stats = data.get("stats", {})
        stats_star = {k: stars(v) for k, v in stats.items()}

        # --- 画像生成 ---
        image_prompt = f"A fantasy racehorse named {name}, {type_} running style, realistic lighting, elegant composition."
        img_response = client.models.generate_content(
            model="gemini-2.5-flash-image",
            contents=[image_prompt],
        )

        image_data = None
        for part in img_response.candidates[0].content.parts:
            if getattr(part, "inline_data", None):
                image_data = part.inline_data.data
                break

        image_url = None
        if image_data:
            bucket = storage_client.bucket(GCS_BUCKET)
            filename = f"output/horse_{uuid.uuid4().hex[:6]}.png"
            blob = bucket.blob(filename)
            blob.upload_from_string(image_data, content_type="image/png")
            image_url = blob.public_url
            print(f"Uploaded: {image_url}", file=sys.stderr)

        return render_template_string(RESULT_HTML, name=name, type=type_, stats=stats_star, image_url=image_url)

    except Exception:
        print(traceback.format_exc(), file=sys.stderr)
        return "Internal Server Error", 500

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8080))
    app.run(host="0.0.0.0", port=port)
