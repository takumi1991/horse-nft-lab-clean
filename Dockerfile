# ベースイメージ
FROM python:3.11-slim

# 環境変数（Cloud Run用）
ENV PYTHONUNBUFFERED=1
ENV PORT=8080

# 作業ディレクトリ
WORKDIR /app

# 依存関係をコピー
COPY requirements.txt .

# パッケージをクリーンにインストール
RUN pip install --no-cache-dir --upgrade pip && \
    pip uninstall -y google-generativeai || true && \
    pip install --no-cache-dir -r requirements.txt

# アプリをコピー
COPY . .

# ポートを公開
EXPOSE 8080

# GunicornでFlask起動
CMD ["gunicorn", "--workers=1", "--threads=8", "--timeout=0", "main:app"]
