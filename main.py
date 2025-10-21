import os, json, uuid, io, sys, traceback
from flask import Flask, render_template_string, request
from google.cloud import storage
import google.generativeai as genai
from PIL import Image

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

# --- スター変換 ---
def stars(score):
    try:
        score = int(score)
    except:
        return "☆☆☆☆☆"
    level = max(1, min(5, round(score / 20)))  # 0-100 → ★1〜5
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
    print("=== /generate called ===", file=sys.stderr)
    try:
        traits = request.form.getlist("traits")
        model = genai.GenerativeModel("gemini-2.5-flash")

        # --- テキスト出力（JSON構造） ---
        prompt_json = f"""
性格タイプ {traits} に基づいて、以下形式のJSONのみを出力してください。
文章や説明は一切不要です。

{{
  "name": "馬名（意味のある造語）",
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

        response = model.generate_content(prompt_json)
        if not response.text:
            raise ValueError("Geminiから応答がありません。")

        # --- JSONパース ---
        try:
            data = json.loads(response.text)
        except json.JSONDecodeError:
            print("Gemini Raw Output:", response.text, file=sys.stderr)
            raise ValueError("Gemini応答をJSONとして解析できません。")

        name = data.get("name", "Unknown Horse")
        type_ = data.get("type", "不明")
        stats = data.get("stats", {})
        stats_star = {k: stars(v) for k, v in stats.items()}

        # --- 画像生成 ---
        image_url = None
        try:
            image_prompt = f"A fantasy racehorse named {name}, {type_} running style, realistic lighting, elegant composition."
            img_model = genai.GenerativeModel("gemini-2.5-flash-image")
            img_response = img_model.generate_content(image_prompt)

            part = next(
                (p for p in img_response.candidates[0].content.parts if getattr(p, "inline_data", None)), None
            )
            if not part:
                raise ValueError("画像データが見つかりません。")

            image_data = part.inline_data.data
            bucket = storage_client.bucket(GCS_BUCKET)
            filename = f"output/horse_{uuid.uuid4().hex[:6]}.png"
            blob = bucket.blob(filename)
            blob.upload_from_string(image_data, content_type="image/png")
            image_url = blob.public_url

        except Exception as img_err:
            print(f"Image generation failed: {img_err}", file=sys.stderr)

        return render_template_string(RESULT_HTML, name=name, type=type_, stats=stats_star, image_url=image_url)

    except Exception as e:
        print(traceback.format_exc(), file=sys.stderr)
        return f"Internal Error: {e}", 500


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8080))
    app.run(host="0.0.0.0", port=port)
