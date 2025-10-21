import os
import uuid
import io
from flask import Flask, render_template, render_template_string, request
from google import genai
from PIL import Image, ImageDraw
from google.cloud import storage
from datetime import timedelta
import sys, traceback

app = Flask(__name__)

# --- 環境変数 ---
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
GCS_BUCKET = os.getenv("GCS_BUCKET")

client = genai.Client(api_key=GEMINI_API_KEY)
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
    print("=== /generate called ===", file=sys.stderr)
    try:
        traits = request.form.getlist("traits")
        prompt_text = f"性格タイプ: {traits} に基づき、理想の馬の特徴を説明してください。"
        image_prompt = f"A detailed artistic illustration of a {traits} horse, fantasy style, vivid colors, highly detailed."

        # --- テキスト生成（説明文） ---
        text_response = client.models.generate_content(
            model="gemini-2.5-flash",
            contents=[prompt_text],
        )
        description = text_response.candidates[0].content.parts[0].text

        # --- 画像生成（Gemini Imageモデル） ---
        image_response = client.models.generate_content(
            model="gemini-2.5-flash-image",
            contents=[image_prompt],
        )

        image_bytes = None
        for part in image_response.candidates[0].content.parts:
            if getattr(part, "inline_data", None) and getattr(part.inline_data, "data", None):
                image_bytes = part.inline_data.data
                break

        if not image_bytes:
            print("❌ Geminiが画像を返しませんでした。テキストのみの応答です。", file=sys.stderr)
            return f"<h1>診断結果</h1><p>{description}</p><p>（画像の生成に失敗しました）</p>", 200

        # --- GCS アップロード ---
        bucket = storage_client.bucket(GCS_BUCKET)
        file_name = f"output/horse_{uuid.uuid4().hex[:8]}.png"
        blob = bucket.blob(file_name)
        blob.upload_from_string(image_bytes, content_type="image/png")
        image_url = blob.public_url

        print(f"✅ 画像アップロード完了: {image_url}", file=sys.stderr)

        return render_template("result.html", description=description, image_url=image_url)

    except Exception:
        print("=== ERROR OCCURRED ===", file=sys.stderr)
        print(traceback.format_exc(), file=sys.stderr)
        return "Internal Server Error", 500


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8080))
    app.run(host="0.0.0.0", port=port)
