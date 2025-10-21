import os
import io
import uuid
from flask import Flask, render_template, render_template_string, request
from google.cloud import storage
from google.genai import Client
from PIL import Image
from io import BytesIO

app = Flask(__name__)

# --- 環境変数 ---
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
GCS_BUCKET = os.getenv("GCS_BUCKET")

client = Client(api_key=GEMINI_API_KEY)
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
        trait_text = ", ".join(traits) if traits else "優しい"

        # --- 説明文生成 ---
        text_prompt = f"性格タイプ: {trait_text} の理想の馬を説明してください。馬の特徴、性格、外見のイメージを含めてください。"
        text_response = client.models.generate_content(
            model="gemini-2.5-flash",
            contents=[text_prompt],
        )
        description = text_response.text.strip()
        print(f"[Gemini Text] {description}", file=sys.stderr)

        # --- 画像生成 ---
        image_prompt = f"{trait_text}な性格の馬のイラスト, 明るい背景, 柔らかい光, ファンタジー風, シンプルでかわいい, 高品質"
        image_response = client.models.generate_content(
            model="gemini-2.5-flash-image",
            contents=[image_prompt],
        )

        image_bytes = None
        for part in image_response.candidates[0].content.parts:
            if hasattr(part, "inline_data") and part.inline_data.data:
                image_bytes = part.inline_data.data
                break

        if not image_bytes:
            print("❌ 画像生成失敗", file=sys.stderr)
            return "画像生成に失敗しました。", 500

        # --- GCSにアップロード ---
        blob_name = f"output/horse_{uuid.uuid4().hex[:8]}.png"
        bucket = storage_client.bucket(GCS_BUCKET)
        blob = bucket.blob(blob_name)
        blob.upload_from_string(image_bytes, content_type="image/png")
        image_url = blob.public_url
        print(f"✅ Image uploaded: {image_url}", file=sys.stderr)

        # --- HTML表示 ---
        RESULT_HTML = f"""
        <!doctype html>
        <html lang="ja">
          <head><meta charset="utf-8"><title>診断結果</title></head>
          <body>
            <h1>🐎 あなたの馬</h1>
            <img src="{image_url}" alt="生成された馬の画像" width="512"><br>
            <p>{description}</p>
            <p><a href="/">もう一度診断する</a></p>
          </body>
        </html>
        """
        return RESULT_HTML

    except Exception:
        print(traceback.format_exc(), file=sys.stderr)
        return "Internal Server Error", 500


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8080))
    app.run(host="0.0.0.0", port=port)
