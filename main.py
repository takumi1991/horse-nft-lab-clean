import os
import json
import re
import sys
import traceback
from flask import Flask, render_template_string, request, jsonify
from google.cloud import storage, secretmanager
import google.generativeai as genai

app = Flask(__name__, static_folder="static", static_url_path="/static")

# --- Secret Managerから値を取得 ---
def get_secret(secret_id: str) -> str:
    client = secretmanager.SecretManagerServiceClient()
    project_id = os.environ.get("GOOGLE_CLOUD_PROJECT", "horse-nft-lab-clean")
    name = f"projects/{project_id}/secrets/{secret_id}/versions/latest"
    response = client.access_secret_version(request={"name": name})
    return response.payload.data.decode("utf-8")

# --- Secrets ---
GEMINI_API_KEY = get_secret("GEMINI_API_KEY")
GCS_BUCKET = get_secret("GCS_BUCKET")

# --- Clients ---
genai.configure(api_key=GEMINI_API_KEY)
storage_client = storage.Client()

PROJECT = os.environ.get("GOOGLE_CLOUD_PROJECT", "horse-nft-lab-clean")

# --- ログ出力関数 ---
def log_sli(event_name: str, success: bool):
    severity = "INFO" if success else "ERROR"
    entry = {
        "severity": severity,
        "sli_event": event_name,
        "success": success,
        "component": "sli"
    }
    sys.stdout.write(json.dumps(entry) + "\n")

# --- HTMLテンプレート ---
HTML_FORM = """
<!doctype html>
<html lang="ja">
<head>
  <meta charset="utf-8">
  <title>🐴 AI競走馬メーカー</title>
  <style>
    body { font-family: system-ui, sans-serif; margin: 0; background: #fafafa; }
    .wrap { display: grid; place-items: center; min-height: 100vh; }
    .card { background: #fff; padding: 24px 32px; border-radius: 16px; box-shadow: 0 4px 20px rgba(0,0,0,0.1); max-width: 720px; width: 100%; }
    h1 { text-align: center; }
    .question { margin: 16px 0; }
    label { margin-right: 12px; }
    button { background: #111; color: #fff; border: 0; padding: 10px 18px; border-radius: 10px; cursor: pointer; }
    button:hover { background: #333; }
  </style>
  <script src="https://unpkg.com/lottie-web/build/player/lottie.min.js"></script>
</head>
<body>
  <div class="wrap">
    <div class="card">
      <h1>🐎 AI競走馬メーカー（SPI性格診断）</h1>
      <form id="quiz" action="/generate" method="post">
        {% for q in questions %}
        <div class="question">
          <b>{{ loop.index }}. {{ q }}</b><br>
          <label><input type="radio" name="q{{ loop.index0 }}" value="1" required> 全く当てはまらない</label>
          <label><input type="radio" name="q{{ loop.index0 }}" value="2"> あまり当てはまらない</label>
          <label><input type="radio" name="q{{ loop.index0 }}" value="3"> どちらともいえない</label>
          <label><input type="radio" name="q{{ loop.index0 }}" value="4"> やや当てはまる</label>
          <label><input type="radio" name="q{{ loop.index0 }}" value="5"> よく当てはまる</label>
        </div>
        <hr>
        {% endfor %}
        <div style="text-align:center;">
          <button id="submitBtn" type="submit">診断する</button>
        </div>
      </form>
    </div>
  </div>

  <!-- ✅ loading overlay -->
  <div id="loading">
    <div class="inner">
      <div id="lottie" aria-label="loading animation"></div>
      <div style="font-size:18px; font-weight:600;">Geminiで生成しています...</div>
    </div>
  </div>

<script>
  let lottieAnim = null;
  const lottieContainer = document.getElementById('lottie');
  const loading = document.getElementById('loading');
  const submitBtn = document.getElementById('submitBtn');
  const form = document.getElementById('quiz');

  // ✅ 一度だけLottieロード
  function preloadLottie() {
    if (lottieAnim) return;
    lottieAnim = lottie.loadAnimation({
      container: lottieContainer,
      renderer: 'svg',
      loop: true,
      autoplay: false,
      path: '/static/racehorse.json'
    });
    lottieAnim.addEventListener('DOMLoaded', () => {
      console.log('Lottie preloaded');
    });
  }

  // ✅ フェードアウト関数
  function fadeOutLoading() {
    loading.style.transition = 'opacity 0.6s ease';
    loading.style.opacity = 0;
    setTimeout(() => {
      loading.style.display = 'none';
      if (lottieAnim) lottieAnim.stop();
    }, 600); // ← transition時間と合わせる
  }

  // ✅ フォーム送信時
  form.addEventListener('submit', () => {
    submitBtn.disabled = true;
    loading.style.display = 'flex';
    loading.style.opacity = 0;
    loading.style.transition = 'opacity 0.3s ease';
    setTimeout(() => {
      loading.style.opacity = 1;
      if (lottieAnim) lottieAnim.play();
    }, 50);
  });

  // ✅ ページ読み込み時
  window.addEventListener('load', preloadLottie, { once: true });

  // ✅ Flask側で生成完了後に呼ぶためのトリガー
  window.fadeOutLoading = fadeOutLoading;
</script>

  <style>
    #loading {
      position: fixed;
      inset: 0;
      background: rgba(255,255,255,0.98);
      display: none;
      align-items: center;
      justify-content: center;
      z-index: 9999;
      opacity: 0;
      transition: opacity 0.6s ease;
    }
    #loading .inner {
      display: grid;
      place-items: center;
      gap: 18px;
      color: #111;
    }
    #lottie {
      width: 240px;
      height: 240px;
    }
  </style>
</body>
</html>
"""

RESULT_HTML = """
<!doctype html>
<html lang="ja">
<head>
  <meta charset="utf-8">
  <title>診断結果</title>
  <style>
    body { font-family: system-ui, sans-serif; text-align: center; background: #fffaf0; margin: 0; }
    .card { display: inline-block; margin-top: 50px; padding: 24px 32px; border-radius: 16px; box-shadow: 0 4px 20px rgba(0,0,0,0.1); background: #fff; }
    h1 { margin-bottom: 10px; }
    img { width: 400px; border-radius: 12px; margin-top: 16px; }
    ul { list-style: none; padding: 0; }
    li { margin: 4px 0; }
    a { display: inline-block; margin-top: 20px; padding: 10px 18px; border-radius: 12px; background: #111; color: #fff; text-decoration: none; }
  </style>
</head>
<body>
  <div class="card">
    <h1>🐴 {{ name }}</h1>
    <p><b>脚質：</b>{{ type }}</p>
    <p><b>性格：</b>{{ personality }}</p>
    {% if image_url %}
      <img src="{{ image_url }}" alt="生成された競走馬の画像">
    {% else %}
      <p>⚠️ 画像生成に失敗しました。</p>
    {% endif %}
    <h3>能力ステータス</h3>
    <ul>
      {% for k, v in stats.items() %}
        <li><b>{{k}}</b>：{{v}}</li>
      {% endfor %}
    </ul>
    <a href="/">もう一度診断する</a>
  </div>
    <!-- ✅ ローディング消去を遅延発火 -->
    <script>
      setTimeout(() => {
        if (window.fadeOutLoading) {
          window.fadeOutLoading();
        }
      }, 300); // 0.3秒待ってからフェードアウト
    </script>
</body>
</html>
"""

# --- 設問一覧 ---
QUESTIONS = [
    "新しい環境にもすぐ慣れる方だ",
    "チームで動くより単独行動が得意",
    "失敗してもすぐ立ち直れる",
    "細かい作業をコツコツ続けるのが得意",
    "他人より競争心が強い",
    "感情より理屈で判断するタイプだ",
    "物事を計画的に進める方だ",
    "難題に挑戦するのが好き",
    "周囲との調和を重視する",
    "急な変化にも柔軟に対応できる"
]

@app.route("/")
def index():
    return render_template_string(HTML_FORM, questions=QUESTIONS)

@app.route("/generate", methods=["POST"])
def generate():
    try:
        # スコア収集
        scores = {f"Q{i+1}": int(request.form.get(f"q{i}", 3)) for i in range(10)}

        # Geminiプロンプト作成
        prompt = f"""
以下の10項目のスコア（1〜5）に基づいて、性格を分析し、競走馬としての特徴を出力してください。
1=全く当てはまらない, 2=あまり当てはまらない, 3=どちらともいえない, 4=やや当てはまる, 5=よく当てはまる。

出力は次のJSON形式にしてください。余分な説明は不要です。
{{
  "name": "馬名（カタカナ）",
  "type": "脚質（逃げ・先行・差し・追込）",
  "personality": "性格を一言でまとめたもの",
  "stats": {{
    "スピード": 数値,
    "スタミナ": 数値,
    "パワー": 数値,
    "敏捷性": 数値,
    "精神力": 数値
  }}
}}

スコア: {json.dumps(scores, ensure_ascii=False)}
"""

        model = genai.GenerativeModel("gemini-2.5-flash")
        response = model.generate_content(prompt)
        raw_text = getattr(response, "text", "").strip()

        # JSON抽出
        match = re.search(r"\{.*\}", raw_text, re.DOTALL)
        if not match:
            raise ValueError("Gemini応答にJSONが含まれていません。")
        data = json.loads(match.group(0))

        # データ取り出し
        name = data.get("name", "名無しの馬")
        type_ = data.get("type", "不明")
        personality = data.get("personality", "性格不明")
        stats = data.get("stats", {})

        # 画像生成
        image_prompt = f"A majestic Japanese racehorse named {name}, {type_} running style, realistic, no humans, no text."
        image_model = genai.GenerativeModel("gemini-2.5-flash-image")
        image_response = image_model.generate_content(image_prompt)

        image_data = None
        if hasattr(image_response, "candidates"):
            for part in image_response.candidates[0].content.parts:
                if getattr(part, "inline_data", None):
                    image_data = part.inline_data.data
                    break

        if image_data:
            filename = f"output/horse_{name}.png"
            bucket = storage_client.bucket(GCS_BUCKET)
            blob = bucket.blob(filename)
            blob.upload_from_string(image_data, content_type="image/png")
            image_url = blob.public_url
        else:
            image_url = None

        log_sli("horse_generate", True)
        return render_template_string(RESULT_HTML, name=name, type=type_, personality=personality, stats=stats, image_url=image_url)

    except Exception:
        log_sli("horse_generate", False)
        print(traceback.format_exc(), file=sys.stderr)
        return "Internal Server Error", 500


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 8080)))
