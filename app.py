from flask import Flask, render_template, request, jsonify, redirect, session
import pandas as pd
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity
import psycopg2
import os
import requests

app = Flask(__name__)
app.secret_key = "secret123"

# ================= DB =================
DATABASE_URL = os.getenv("DATABASE_URL")
conn = psycopg2.connect(DATABASE_URL)
conn.autocommit = True
cursor = conn.cursor()

cursor.execute("""
CREATE TABLE IF NOT EXISTS user_history (
    id SERIAL PRIMARY KEY,
    username TEXT,
    track_name TEXT,
    artist_name TEXT,
    action TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
)
""")

# ================= DATA =================
data = pd.read_csv("tcc_ceds_music_sample.csv")
data.fillna("", inplace=True)

data["combined"] = data["genre"] + " " + data["artist_name"] + " " + data["track_name"]

tfidf = TfidfVectorizer(stop_words="english")
matrix = tfidf.fit_transform(data["combined"])
similarity = cosine_similarity(matrix)

# ================= HELPERS =================
def get_song_data(song, artist):
    try:
        url = f"https://itunes.apple.com/search?term={song} {artist}&limit=1"
        res = requests.get(url).json()
        if res["resultCount"] > 0:
            item = res["results"][0]
            return item["artworkUrl100"], item.get("previewUrl", "")
    except:
        pass
    return "https://via.placeholder.com/300", ""

def recommend(song):
    match = data[data["track_name"].str.lower().str.contains(song.lower())]
    if match.empty:
        return []

    idx = match.index[0]
    scores = list(enumerate(similarity[idx]))
    scores = sorted(scores, key=lambda x: x[1], reverse=True)[1:10]

    result = []
    for i, _ in scores:
        row = data.iloc[i]
        img, preview = get_song_data(row["track_name"], row["artist_name"])
        result.append({
            "name": row["track_name"],
            "artist": row["artist_name"],
            "image": img,
            "preview": preview
        })
    return result

def save(user, song, action):
    row = data[data["track_name"].str.lower().str.contains(song.lower())]
    if row.empty:
        return
    row = row.iloc[0]
    cursor.execute(
        "INSERT INTO user_history (username, track_name, artist_name, action) VALUES (%s,%s,%s,%s)",
        (user, row["track_name"], row["artist_name"], action)
    )

# ================= PLAYLIST =================
playlist_store = {}

@app.route("/add_to_playlist", methods=["POST"])
def add_playlist():
    data_req = request.get_json()
    user = session["user"]

    if user not in playlist_store:
        playlist_store[user] = []

    playlist_store[user].append(data_req)
    return jsonify({"ok": True})

@app.route("/get_playlist")
def get_playlist():
    return jsonify(playlist_store.get(session["user"], []))

# ================= CHATBOT =================
@app.route("/chat", methods=["POST"])
def chat():
    msg = request.json["message"].lower()
    songs = recommend(msg)
    return jsonify(songs)

# ================= HOME =================
@app.route("/", methods=["GET","POST"])
def home():
    if "user" not in session:
        return redirect("/login")

    recs = []
    if request.method == "POST":
        recs = recommend(request.form["song"])

    # HISTORY
    cursor.execute("""
        SELECT track_name, artist_name FROM user_history
        WHERE username=%s ORDER BY id DESC LIMIT 10
    """,(session["user"],))

    history = []
    for h in cursor.fetchall():
        img, preview = get_song_data(h[0], h[1])
        history.append({"name":h[0],"artist":h[1],"image":img,"preview":preview})

    return render_template("index.html", recs=recs, history=history)

# ================= LOGIN =================
@app.route("/login", methods=["GET","POST"])
def login():
    if request.method=="POST":
        session["user"] = request.form["username"]
        return redirect("/")
    return render_template("login.html")

@app.route("/logout")
def logout():
    session.clear()
    return redirect("/login")

# ================= ACTIONS =================
@app.route("/play", methods=["POST"])
def play():
    save(session["user"], request.json["song"], "play")
    return jsonify({"ok":True})

@app.route("/like", methods=["POST"])
def like():
    save(session["user"], request.json["song"], "like")
    return jsonify({"ok":True})

# ================= RUN =================
if __name__ == "__main__":
    app.run(debug=True)
