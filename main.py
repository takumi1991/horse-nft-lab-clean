import os
import json
import uuid
from flask import Flask, render_template_string, request
import google.generativeai as genai
from datetime import timedelta
from google.cloud import storage
import io
from PIL import Image, ImageDraw

app = Flask(__name__)

# --- 環境変数 ---
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
GCS_BUCKET = os.getenv("GCS_BUCKET")

genai.configure(api_key=GEMINI_API_KEY)
storage_client = storage.Client()


def stars(score):
    """0〜100を★5段階に変換"""
    level = round(score / 20)
    return "★" * level + "☆" * (5 - level)


# --- HTML ---
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

RESULT_HTML = """
<!doctype html>
<html lang="ja">
  <head><meta charset="utf-8"><title>診断結果</title></head>
  <body>
    <h1>🐎 {{name}}</h1>
    <p><strong>脚質:</strong> {{type}}</p>
    <img src="{{image_url}}" width="300"><br>
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

        # Gemini出力をJSONで要求
        prompt = f"""
性格タイプ {traits} に基づいて、以下形式のJSONを返してください。
馬名と脚質、そして8つの能力値（0〜100）を含めてください。

{{
  "name": "馬名",
  "type": "脚質（逃げ・先行・差し・追込）",
  "stats": {{
    "Speed": 数値,
    "Stamina": 数値,
    "Power": 数値,
    "Agility": 数値,
    "Intelligence": 数値,
    "Temperament": 数値,
    "Endurance": 数値,
    "Charm": 数値
  }}
}}
        """

        model = genai.GenerativeModel("gemini-2.5-flash")
        response = model.generate_content(prompt)
        text = response.text.strip()

        # JSONパース
        data = json.loads(text)
        name = data.get("name", "Unknown Horse")
        type_ = data.get("type", "不明")
        stats = data.get("stats", {})

        # 星表示に変換
        stats_star = {k: stars(v) for k, v in stats.items()}

        # --- ダミー画像生成（馬のサムネ） ---
        img = Image.new("RGB", (512, 512), "white")
        draw = ImageDraw.Draw(img)
        draw.text((20, 200), f"{name}\n({type_})", fill=(0, 0, 0))
        buf = io.BytesIO()
        img.save(buf, format="PNG")

        bucket = storage_client.bucket(GCS_BUCKET)
        filename = f"output/horse_{uuid.uuid4().hex[:6]}.png"
        blob = bucket.blob(filename)
        blob.upload_from_string(buf.getvalue(), content_type="image/png")
        image_url = blob.public_url

        return render_template_string(RESULT_HTML, name=name, type=type_, stats=stats_star, image_url=image_url)

    except Exception as e:
        import traceback, sys
        print(traceback.format_exc(), file=sys.stderr)
        return f"Internal Error: {str(e)}", 500


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8080))
    app.run(host="0.0.0.0", port=port)
