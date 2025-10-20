from flask import Flask

app = Flask(__name__)

@app.route("/")
def home():
    return "✅ horse-nft-lab-clean is alive!!"

if __name__ == "__main__":
    import os
    app.run(host="0.0.0.0", port=int(os.getenv("PORT", 8080)))
