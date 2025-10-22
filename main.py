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
from dotenv import load_dotenv
load_dotenv()

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

HTML_FORM = """
<!doctype html>
<html lang="ja">
<head>
  <meta charset="utf-8">
  <title>AI競走馬メーカー</title>
  <script src="https://unpkg.com/lottie-web/build/player/lottie.min.js"></script>
  <style>
    :root { color-scheme: light dark; }
    body{margin:0;font-family:system-ui,-apple-system,Segoe UI,Roboto,Helvetica,Arial,sans-serif;}
    .wrap{min-height:100dvh;display:grid;place-items:center;padding:24px;}
    .card{max-width:720px;width:100%;text-align:center;padding:24px 28px;border:1px solid #e6e6e6;border-radius:16px;box-shadow:0 6px 20px rgba(0,0,0,.06)}
    form{margin-top:12px}
    .traits{display:flex;flex-wrap:wrap;gap:12px;justify-content:center;margin:10px 0 18px}
    .traits label{display:flex;align-items:center;gap:6px;padding:8px 12px;border:1px solid #ddd;border-radius:12px;cursor:pointer}
    button[type="submit"]{padding:10px 18px;border-radius:12px;border:0;background:#111;color:#fff;font-weight:600;cursor:pointer}
    button[disabled]{opacity:.6;cursor:wait}
    /* loading overlay */
    #loading{position:fixed;inset:0;background:rgba(255,255,255,.92);display:none;align-items:center;justify-content:center;z-index:9999}
    #loading .inner{display:grid;place-items:center;gap:14px}
    #lottie{width:260px;height:260px}
    .hint{font-size:14px;color:#666}
  </style>
</head>
<body>
  <div class="wrap">
    <div class="card">
      <h1>🐴 AI競走馬メーカー</h1>
      <p>あなたの性格タイプを選んでください：</p>
      <form id="quiz" action="/generate" method="post">
        <div class="traits">
          <label><input type="checkbox" name="traits" value="brave">勇敢</label>
          <label><input type="checkbox" name="traits" value="calm">落ち着き</label>
          <label><input type="checkbox" name="traits" value="agile">俊敏</label>
          <label><input type="checkbox" name="traits" value="loyal">忠実</label>
          <label><input type="checkbox" name="traits" value="clever">賢い</label>
        </div>
        <button id="submitBtn" type="submit">診断開始</button>
      </form>
      <p class="hint">生成には数秒かかります。アニメーションが止まったら結果が表示されます。</p>
    </div>
  </div>

  <!-- loading overlay -->
  <div id="loading">
    <div class="inner">
      <div id="lottie" aria-label="loading animation"></div>
      <div>生成中…少々お待ちください</div>
    </div>
  </div>

  <script>
    // 1) 事前に Lottie をロード（ローカル静的ファイル）
    let lottieAnim = null;
    const lottieContainer = document.getElementById('lottie');
    function ensureLottie() {
      if (lottieAnim) return lottieAnim;
      lottieAnim = lottie.loadAnimation({
        container: lottieContainer,
        renderer: 'svg',
        loop: true,
        autoplay: false,
        // ローカルの静的ファイルを配信（Flask の /static 直配）
        path: '/static/horse_runner.json'
      });
      return lottieAnim;
    }

    // 2) 送信時にオーバーレイを表示＆アニメ再生
    const form = document.getElementById('quiz');
    const loading = document.getElementById('loading');
    const submitBtn = document.getElementById('submitBtn');

    form.addEventListener('submit', () => {
      submitBtn.disabled = true;
      loading.style.display = 'flex';
      ensureLottie().play();
    });

    // 念のため、ページ表示時にも先読みしておく
    window.addEventListener('load', ensureLottie, { once: true });
  </script>
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
    :root { color-scheme: light dark; }
    body{margin:0;font-family:system-ui,-apple-system,Segoe UI,Roboto,Helvetica,Arial,sans-serif;}
    .wrap{min-height:100dvh;display:grid;place-items:center;padding:24px}
    .card{max-width:860px;width:100%;text-align:center;padding:24px 28px;border:1px solid #e6e6e6;border-radius:16px;box-shadow:0 6px 20px rgba(0,0,0,.06)}
    .grid{display:grid;gap:18px;justify-items:center}
    img{max-width:520px;width:100%;height:auto;border-radius:12px;border:1px solid #eee}
    ul{list-style:none;padding:0;margin:0;display:grid;gap:8px;justify-items:center}
    li{padding:6px 10px;border:1px solid #eee;border-radius:10px;min-width:260px}
    a.btn{display:inline-block;margin-top:16px;padding:10px 18px;border-radius:12px;background:#111;color:#fff;text-decoration:none;font-weight:600}
  </style>
</head>
<body>
  <div class="wrap">
    <div class="card">
      <div class="grid">
        <div>
          <h1>🐎 {{name}}</h1>
          <p><b>脚質:</b> {{type}}</p>
        </div>
        {% if image_url %}
          <img src="{{image_url}}" alt="生成された競走馬の画像">
        {% else %}
          <p>⚠️ 画像生成に失敗しました。</p>
        {% endif %}
        <div>
          <h3>能力ステータス</h3>
          <ul>
            {% for k, v in stats.items() %}
              <li><b>{{k}}</b>： {{v}}</li>
            {% endfor %}
          </ul>
        </div>
        <a class="btn" href="/">もう一度診断する</a>
      </div>
    </div>
  </div>
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

        # --- NFTミント処理 ---
        wallet_address = "ご主人様のMetaMaskアドレス"  # 例: 0xA123...F9
        mint_result = mint_nft(image_url, name, wallet_address)

        print("NFT Mint Result:", mint_result)

        return render_template_string(RESULT_HTML, name=name, type=type_, stats=stats_star, image_url=image_url)

    except Exception:
        print(traceback.format_exc(), file=sys.stderr)
        return "Internal Server Error", 500

import requests

MORALIS_API_KEY = os.getenv("MORALIS_API_KEY")

def mint_nft(image_url, name, wallet_address):
    """
    Moralis APIを使ってPolygon AmoyにNFTをミント
    """
    url = "https://deep-index.moralis.io/api/v2/nft/mint"
    headers = {
        "accept": "application/json",
        "X-API-Key": MORALIS_API_KEY,
        "content-type": "application/json"
    }
    payload = {
        "chain": "amoy",
        "to_address": wallet_address,
        "name": name,
        "description": f"{name} - AI generated racehorse NFT",
        "image": image_url
    }

    response = requests.post(url, headers=headers, json=payload)
    print("Mint response:", response.text)
    return response.json()


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8080))
    app.run(host="0.0.0.0", port=port)
