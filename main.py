import os
import uuid
import io
from flask import Flask, render_template, render_template_string, request
from google.cloud import storage
import google.generativeai as genai

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
        trait_text = ", ".join(traits) if traits else "優しい"
        prompt = f"性格: {trait_text} の馬のキャラクターイラストを生成してください。シンプルで明るい背景。"

        # ✅ 説明文をまず生成
        model_text = genai.GenerativeModel("gemini-2.5-flash")
        desc_response = model_text.generate_content(f"{trait_text}な性格の理想の馬の特徴を説明してください。")
        description = desc_response.text

        # ✅ 画像生成（Gemini）
        model_image = genai.GenerativeModel("gemini-2.5-flash")
        image_response = model_image.generate_content(
            [prompt],
            generation_config={"response_mime_type": "image/png"}
        )

        # ✅ バイナリデータとして取得
        image_data = image_response._result.candidates[0].content.parts[0].inline_data.data
        image_bytes = io.BytesIO(image_data)

        # ✅ GCSアップロード
        bucket = storage_client.bucket(GCS_BUCKET)
        blob_name = f"output/horse_{uuid.uuid4().hex[:8]}.png"
        blob = bucket.blob(blob_name)
        blob.upload_from_string(image_bytes.getvalue(), content_type="image/png")

        image_url = blob.public_url
        print(f"Image uploaded: {image_url}", file=sys.stderr)

        return render_template("result.html", description=description, image_url=image_url)

    except Exception:
        print("=== ERROR OCCURRED ===", file=sys.stderr)
        print(traceback.format_exc(), file=sys.stderr)
        return "Internal Server Error", 500


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8080))
    app.run(host="0.0.0.0", port=port)
