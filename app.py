import json
from pathlib import Path

from flask import Flask, jsonify, request

from dispatcher import classify
from monitoring import MAX_TEXTS, cluster_texts

BASE = Path(__file__).resolve().parent
app = Flask(__name__, static_folder="static", static_url_path="")


@app.get("/")
def index():
    return app.send_static_file("index.html")


@app.get("/api/cases")
def cases():
    return jsonify(json.loads((BASE / "cases_training.json").read_text(encoding="utf-8")))


@app.post("/api/classify")
def classify_api():
    data = request.get_json(silent=True) or {}
    text = data.get("text")
    if not isinstance(text, str) or not 1 <= len(text.strip()) <= 1000:
        return jsonify({"error": "Введите обращение длиной от 1 до 1000 символов."}), 400
    try:
        return jsonify(classify(text.strip()))
    except (RuntimeError, NotImplementedError, ValueError, KeyError, TypeError, json.JSONDecodeError) as error:
        return jsonify({"error": str(error)}), 502


@app.post("/api/monitoring/clusters")
def monitoring_clusters():
    data = request.get_json(silent=True) or {}
    texts = data.get("texts")
    if not isinstance(texts, list) or not texts:
        return jsonify({"error": "Передайте список обращений (texts)."}), 400
    if len(texts) > MAX_TEXTS:
        texts = texts[-MAX_TEXTS:]
    try:
        return jsonify(cluster_texts(texts))
    except (RuntimeError, ValueError, KeyError, TypeError, json.JSONDecodeError) as error:
        return jsonify({"error": str(error)}), 502


if __name__ == "__main__":
    app.run(host="127.0.0.1", port=5000, debug=False)
