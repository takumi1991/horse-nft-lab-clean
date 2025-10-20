
# ベースイメージ
FROM python:3.11-slim

# 作業ディレクトリ
WORKDIR /app

# 依存関係をコピーしてインストール
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# アプリ本体をコピー
COPY . .

# Cloud Run でリッスンするポート
ENV PORT=8080
EXPOSE 8080

# 実行コマンド（Flask or FastAPI の場合）
CMD ["python", "main.py"]
