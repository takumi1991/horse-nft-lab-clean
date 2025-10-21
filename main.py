import os
import uuid
import io
import json
import re
import sys, traceback
from flask import Flask, render_template_string, request
import google.generativeai as genai
from PIL import Image
from google.cloud import storage

app = Flask(__name__)

# --- 環境変数 ---
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
GCS_BUCKET = os.getenv("GCS_BUCKET")
if not GEMINI_API_KEY:
    raise RuntimeError("環境変数 GEMINI_API_KEY が設定されていません。")
if not GCS_BUCKET:
    raise RuntimeError("環境変数 GCS_BUCKET が設定されていません。")

genai.configure(api_key=GEMINI_API_KEY)
storage_client = storage.Client()

# --- 星評価変換 ---
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
<head>
  <meta charset="utf-8">
  <title>AI競走馬メーカー</title>
  <script>
    function showLoading() {
      document.getElementById('form-section').style.display = 'none';
      document.getElementById('loading-section').style.display = 'block';
    }
  </script>
  <style>
    body { text-align:center; font-family:sans-serif; background:#fffaf0; }
    #loading-section { display:none; margin-top:50px; }
  </style>
  <!-- Lottie プレイヤー -->
  <script src="https://unpkg.com/@lottiefiles/lottie-player@latest/dist/lottie-player.js"></script>
</head>
<body>
  <h1>🐴 AI競走馬メーカー</h1>

  <div id="form-section">
    <form action="/generate" method="post" onsubmit="showLoading()">
      <p>あなたの性格タイプを選んでください：</p>
      <input type="checkbox" name="traits" value="brave">勇敢
      <input type="checkbox" name="traits" value="calm">落ち着き
      <input type="checkbox" name="traits" value="agile">俊敏
      <input type="checkbox" name="traits" value="loyal">忠実
      <input type="checkbox" name="traits" value="clever">賢い
      <p><input type="submit" value="診断開始"></p>
    </form>
  </div>

  <div id="loading-section">
    <h2>結果を生成中です…</h2>
    <lottie-player src="/static/horse_runner.json" background="transparent" speed="1" style="width:300px;height:300px;margin:auto;" loop autoplay></lottie-player>
    <p>AIがあなたの理想の競走馬を生み出しています。</p>
  </div>
</body>
</html>
"""

RESULT_HTML = """
<!doctype html>
<html lang="ja">
<head>
  <meta charset="utf-8"><title>AI競走馬結果</title>
  <style>
    body { text-align:center; font-family:sans-serif; background:#fffaf0; }
    img { border-radius:10px; margin-top:15px; }
  </style>
</head>
<body>
  <h1>🐎 {{name}}</h1>
  <p><b>脚質:</b> {{type}}</p>
  {% if image_url %}
    <img src="{{image_url}}" width="400"><br><br>
  {% else %}
    <p>⚠️ 画像生成に失敗しました。</p>
  {% endif %}
  <h3>能力ステータス</h3>
  <ul style="list-style:none; padding:0;">
    {% for k, v in stats.items() %}
      <li><b>{{k}}</b>: {{v}}</li>
    {% endfor %}
  </ul>
  <p><a href="/">もう一度診断する</a></p>
</body>
</html>
"""

RESULT_HTML = """
<!doctype html>
<html lang="ja">
<head>
  <meta charset="utf-8">
  <title>AI競走馬結果</title>
  <style>
    body {
      font-family: 'Hiragino Sans', 'Noto Sans JP', sans-serif;
      text-align: center;
      background-color: #fafafa;
      margin: 40px;
    }
    h1 {
      font-size: 2em;
      margin-bottom: 0.2em;
    }
    img {
      display: block;
      margin: 20px auto;
      border-radius: 10px;
      box-shadow: 0 0 10px rgba(0,0,0,0.2);
    }
    ul {
      list-style: none;
      padding: 0;
      display: inline-block;
      text-align: left;
    }
    li {
      margin: 4px 0;
      font-size: 1.1em;
    }
    p {
      font-size: 1.1em;
    }
    a {
      color: #007bff;
      text-decoration: none;
    }
    a:hover {
      text-decoration: underline;
    }
  </style>
</head>
<body>
  <h1>🐎 {{name}}</h1>
  <p><b>脚質:</b> {{type}}</p>
  {% if image_url %}
    <img src="{{image_url}}" width="500">
  {% else %}
    <p>⚠️ 画像生成に失敗しました。</p>
  {% endif %}
  <h3>能力ステータス</h3>
  <ul>
    {% for k, v in stats.items() %}
      <li><b>{{k}}:</b> {{v}}</li>
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

        # --- JSON抽出（空・非JSON対策） ---
        raw_text = ""
        if hasattr(response, "text") and response.text:
            raw_text = response.text
        elif hasattr(response, "candidates") and response.candidates:
            try:
                raw_text = response.candidates[0].content.parts[0].text
            except Exception:
                pass

        if not raw_text.strip():
            raise ValueError("Geminiの応答が空です。")

        match = re.search(r'\{.*\}', raw_text, re.DOTALL)
        if not match:
            print("⚠️ Gemini出力（非JSON）:", raw_text[:200], file=sys.stderr)
            raise ValueError("Geminiが有効なJSONを返しませんでした。")

        data = json.loads(match.group(0))

        name = data.get("name", "Unknown Horse")
        type_ = data.get("type", "不明")
        stats = data.get("stats", {})
        stats_star = {k: stars(v) for k, v in stats.items()}

        # --- 画像生成 ---
        image_prompt = f"A realistic racehorse named {name}, running alone on a professional Japanese race track, {type_} running style, no humans, no jockeys, no text, no logo, realistic lighting, motion blur, dirt flying, detailed photo style."
        image_model = genai.GenerativeModel("gemini-2.5-flash-image")
        img_response = image_model.generate_content(image_prompt)

        image_data = None
        if hasattr(img_response, "candidates"):
            for part in img_response.candidates[0].content.parts:
                if getattr(part, "inline_data", None) and getattr(part.inline_data, "data", None):
                    image_data = part.inline_data.data
                    break

        if not image_data:
            image_url = None
        else:
            bucket = storage_client.bucket(GCS_BUCKET)
            filename = f"output/horse_{uuid.uuid4().hex[:6]}.png"
            blob = bucket.blob(filename)
            blob.upload_from_string(image_data, content_type="image/png")
            image_url = blob.public_url

        return render_template_string(RESULT_HTML, name=name, type=type_, stats=stats_star, image_url=image_url)

    except Exception:
        print(traceback.format_exc(), file=sys.stderr)
        return "Internal Server Error", 500


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8080))
    app.run(host="0.0.0.0", port=port)
