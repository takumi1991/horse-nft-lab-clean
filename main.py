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
    import traceback, sys
    print("=== /generate called ===", file=sys.stderr)
    try:
        # ✅ フォームデータの取得
        traits = request.form.to_dict()
        print(f"Traits received: {traits}", file=sys.stderr)

        # ✅ Gemini API キー確認
        api_key = os.getenv("GEMINI_API_KEY")
        if not api_key:
            print("ERROR: GEMINI_API_KEY not set", file=sys.stderr)
            return "Internal error: missing API key", 500

        import google.generativeai as genai
        genai.configure(api_key=api_key)
        model = genai.GenerativeModel(model_name="gemini-1.5-flash")

        # ✅ 馬の説明文を生成
        prompt = "性格診断の結果に基づいて理想の馬の特徴を説明してください: " + str(traits)
        response = model.generate_content(prompt)
        description = response.text
        print(f"Gemini response: {description}", file=sys.stderr)

        # ✅ 画像生成（仮にテキストを画像に）
        from PIL import Image, ImageDraw, ImageFont
        img = Image.new("RGB", (512, 512), color=(255, 255, 255))
        draw = ImageDraw.Draw(img)
        draw.text((10, 10), description[:100], fill=(0, 0, 0))

        # ✅ GCS アップロード処理
        from google.cloud import storage
        bucket_name = os.getenv("GCS_BUCKET")
        if not bucket_name:
            print("ERROR: GCS_BUCKET not set", file=sys.stderr)
            return "Internal error: missing bucket", 500

        storage_client = storage.Client()
        bucket = storage_client.bucket(bucket_name)
        blob = bucket.blob("output/horse_image.png")

        from io import BytesIO
        buf = BytesIO()
        img.save(buf, format="PNG")
        blob.upload_from_string(buf.getvalue(), content_type="image/png")
        print(f"Image uploaded to GCS: {blob.public_url}", file=sys.stderr)

        return render_template("result.html", description=description, image_url=blob.public_url)

    except Exception as e:
        print("=== ERROR OCCURRED ===", file=sys.stderr)
        print(traceback.format_exc(), file=sys.stderr)
        return "Internal Server Error", 500

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8080))
    app.run(host="0.0.0.0", port=port)
