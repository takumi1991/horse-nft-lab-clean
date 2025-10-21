import os, json, uuid, io
from flask import Flask, render_template_string, request
from google.cloud import storage
import google.generativeai as genai
from PIL import Image, ImageDraw

app = Flask(__name__)

# --- 環境変数 ---
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
GCS_BUCKET = os.getenv("GCS_BUCKET")

genai.configure(api_key=GEMINI_API_KEY)
storage_client = storage.Client()

def stars(score):
    level = round(score / 20)
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
    <img src="{{image_url}}" width="400"><br><br>
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
        model = genai.GenerativeModel("gemini-2.5-flash")

        # --- テキスト出力（JSON構造） ---
        prompt_json = f"""
性格タイプ {traits} に基づいて、以下形式のJSONを出力してください。

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
        response = model.generate_content(prompt_json)
        data = json.loads(response.text)
        name = data.get("name", "Unknown Horse")
        type_ = data.get("type", "不明")
        stats = data.get("stats", {})
        stats_star = {k: stars(v) for k, v in stats.items()}

        # --- イラスト生成 ---
        image_prompt = f"Generate a fantasy racehorse named {name}, with a {type_} running style, elegant lighting and dynamic pose."
        img_response = genai.GenerativeModel("gemini-2.5-flash-image").generate_content(image_prompt)
        part = next((p for p in img_response.candidates[0].content.parts if hasattr(p, "inline_data")), None)
        image_data = part.inline_data.data

        # --- GCSアップロード ---
        bucket = storage_client.bucket(GCS_BUCKET)
        filename = f"output/horse_{uuid.uuid4().hex[:6]}.png"
        blob = bucket.blob(filename)
        blob.upload_from_string(image_data, content_type="image/png")
        image_url = blob.public_url

        return render_template_string(RESULT_HTML, name=name, type=type_, stats=stats_star, image_url=image_url)

    except Exception as e:
        import traceback, sys
        print(traceback.format_exc(), file=sys.stderr)
        return f"Internal Error: {e}", 500

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8080))
    app.run(host="0.0.0.0", port=port)
