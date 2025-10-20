import os
import json
import uuid
from flask import Flask, render_template_string, request
import google.generativeai as genai
from google.cloud import storage
from datetime import datetime
from PIL import Image, ImageDraw, ImageFont
import io

app = Flask(__name__)

# --- 環境変数 ---
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
GCS_BUCKET = os.getenv("GCS_BUCKET")

genai.configure(api_key=GEMINI_API_KEY)
storage_client = storage.Client()

# --- HTMLテンプレート ---
HTML_FORM = """
<!doctype html>
<html lang="ja">
  <head><meta charset="utf-8"><title>馬性格診断</title></head>
  <body>
    <h1>🐴 あなたの理想の馬を診断</h1>
    <form action="/generate" method="post">
      <p>性格タイプを選んでください：</p>
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

# --- 結果ページ ---
RESULT_HTML = """
<!doctype html>
<html lang="ja">
  <head><meta charset="utf-8"><title>診断結果</title></head>
  <body>
    <h1>🐎 あなたの馬：{{name}}</h1>
    <img src="{{image_url}}" width="300"><br>
    <p>{{description}}</p>
    <p><a href="/">もう一度診断する</a></p>
  </body>
</html>
"""

@app.route("/")
def index():
    return render_template_string(HTML_FORM)

@app.route("/generate", methods=["POST"])
def generate():
    traits = request.form.getlist("traits")
    if not traits:
        return "少なくとも1つ選んでください", 400

    prompt = f"次の特徴を持つ馬の名前と性格と能力を考えてください: {', '.join(traits)}。"

    # Geminiによる生成
    model = genai.GenerativeModel("gemini-1.5-flash")
    response = model.generate_content(prompt)
    text = response.text.strip() if response and response.text else "生成失敗"

    # 仮の馬名と能力値
    horse_name = f"Horse-{uuid.uuid4().hex[:6]}"
    desc = text

    # 画像生成（簡易版）
    img = Image.new("RGB", (400, 400), (200, 230, 255))
    d = ImageDraw.Draw(img)
    d.text((20, 180), f"{horse_name}\n{', '.join(traits)}", fill=(0, 0, 0))

    # GCSに保存
    bucket = storage_client.bucket(GCS_BUCKET)
    image_blob = bucket.blob(f"{horse_name}.png")
    metadata_blob = bucket.blob(f"{horse_name}.json")

    # 画像アップロード
    with io.BytesIO() as img_bytes:
        img.save(img_bytes, format="PNG")
        img_bytes.seek(0)
        image_blob.upload_from_file(img_bytes, content_type="image/png")

    # メタデータアップロード
    metadata = {
        "name": horse_name,
        "traits": traits,
        "description": desc,
        "created_at": datetime.utcnow().isoformat()
    }
    metadata_blob.upload_from_string(json.dumps(metadata), content_type="application/json")

    image_url = f"https://storage.googleapis.com/{GCS_BUCKET}/{horse_name}.png"

    return render_template_string(RESULT_HTML, name=horse_name, description=desc, image_url=image_url)

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8080))
    app.run(host="0.0.0.0", port=port)
