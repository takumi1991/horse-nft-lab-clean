import os
import json
import uuid
from flask import Flask, render_template, render_template_string, request
import google.generativeai as genai
from google.cloud import storage
from datetime import datetime
from PIL import Image, ImageDraw
import io

app = Flask(__name__)

# --- 環境変数 ---
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
GCS_BUCKET = os.getenv("GCS_BUCKET")

genai.configure(api_key=GEMINI_API_KEY)
storage_client = storage.Client()

# --- HTMLフォーム ---
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

@app.route("/")
def index():
    return render_template_string(HTML_FORM)

@app.route("/generate", methods=["POST"])
def generate():
    import traceback, sys
    print("=== /generate called ===", file=sys.stderr)
    try:
        traits = request.form.getlist("traits")
        prompt = f"性格タイプ: {traits} に基づき、理想の馬の特徴を説明してください。"

        model = genai.GenerativeModel("gemini-2.5-flash")
        response = model.generate_content(prompt)
        description = response.text

        # 画像生成（仮：テキストを画像化）
        img = Image.new("RGB", (1024, 1024), "white")
        draw = ImageDraw.Draw(img)
        draw.rectangle((0, 0, 1024, 120), fill=(240, 240, 240))
        draw.text((20, 40), description[:60], fill=(0, 0, 0))

        # ✅ GCS アップロード（public_url使用）
        bucket = storage_client.bucket(GCS_BUCKET)
        blob_name = f"output/horse_{uuid.uuid4().hex[:8]}.png"
        blob = bucket.blob(blob_name)

        buf = io.BytesIO()
        img.save(buf, format="PNG")
        blob.upload_from_string(buf.getvalue(), content_type="image/png")

        # ✅ 公開URLを取得
        image_url = blob.public_url
        print(f"Image uploaded to GCS: {image_url}", file=sys.stderr)

        img.close()
        del img

        return render_template("result.html", description=description, image_url=image_url)

    except Exception:
        print(traceback.format_exc(), file=sys.stderr)
        return "Internal Server Error", 500


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8080))
    app.run(host="0.0.0.0", port=port)
