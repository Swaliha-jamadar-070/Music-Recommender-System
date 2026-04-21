from flask import Flask, render_template, request, jsonify, redirect, session
import pandas as pd
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity
import psycopg2
import os
import requests

app = Flask(__name__)
app.secret_key = "secret123"

# DB
DATABASE_URL = os.getenv("DATABASE_URL")
conn = psycopg2.connect(DATABASE_URL)
conn.autocommit = True
cursor = conn.cursor()

# TABLE
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

# LOAD DATA
data = pd.read_csv("tcc_ceds_music_sample.csv")
data.fillna("", inplace=True)

data["combined"] = data["genre"] + " " + data["artist_name"] + " " + data["track_name"]

tfidf = TfidfVectorizer(stop_words="english")
matrix = tfidf.fit_transform(data["combined"])
similarity = cosine_similarity(matrix)

# 🎧 GET IMAGE + PREVIEW
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

# 🤖 RECOMMEND
def recommend(song):
    match = data[data["track_name"].str.lower().str.contains(song.lower())]
    if match.empty:
        return []

    idx = match.index[0]
    scores = list(enumerate(similarity[idx]))
    scores = sorted(scores, key=lambda x: x[1], reverse=True)[1:10]

    result = []
    for i, s in scores:
        row = data.iloc[i]
        img, preview = get_song_data(row["track_name"], row["artist_name"])

        result.append({
            "name": row["track_name"],
            "artist": row["artist_name"],
            "image": img,
            "preview": preview
        })
    return result

# 💾 SAVE HISTORY
def save(user, song, action):
    row = data[data["track_name"].str.lower().str.contains(song.lower())]
    if row.empty:
        return
    row = row.iloc[0]

    cursor.execute(
        "INSERT INTO user_history (username, track_name, artist_name, action) VALUES (%s,%s,%s,%s)",
        (user, row["track_name"], row["artist_name"], action)
    )

# 🏠 HOME
@app.route("/", methods=["GET","POST"])
def home():
    if "user" not in session:
        return redirect("/login")

    user = session["user"]
    recs = []

    if request.method == "POST":
        recs = recommend(request.form["song"])

    # HISTORY
    cursor.execute("""
        SELECT track_name, artist_name 
        FROM user_history 
        WHERE username=%s 
        ORDER BY id DESC LIMIT 10
    """,(user,))
    
    history_raw = cursor.fetchall()
    history = []

    for h in history_raw:
        img, preview = get_song_data(h[0], h[1])
        history.append({
            "name": h[0],
            "artist": h[1],
            "image": img,
            "preview": preview
        })

    # TRENDING
    cursor.execute("""
        SELECT track_name, COUNT(*) 
        FROM user_history 
        GROUP BY track_name 
        ORDER BY COUNT(*) DESC LIMIT 10
    """)
    
    trending_raw = cursor.fetchall()
    trending = []

    for t in trending_raw:
        row = data[data["track_name"].str.lower().str.contains(t[0].lower())]
        if not row.empty:
            artist = row.iloc[0]["artist_name"]
            img, preview = get_song_data(t[0], artist)

            trending.append({
                "name": t[0],
                "artist": artist,
                "image": img,
                "preview": preview
            })

    return render_template("index.html",
                           recs=recs,
                           history=history,
                           trending=trending)

# LOGIN
@app.route("/login", methods=["GET","POST"])
def login():
    if request.method == "POST":
        session["user"] = request.form["username"]
        return redirect("/")
    return render_template("login.html")

@app.route("/logout")
def logout():
    session.clear()
    return redirect("/login")

# PLAY
@app.route("/play", methods=["POST"])
def play():
    data_req = request.get_json()
    save(session["user"], data_req["song"], "play")
    return jsonify({"ok": True})

# LIKE
@app.route("/like", methods=["POST"])
def like():
    data_req = request.get_json()
    save(session["user"], data_req["song"], "like")
    return jsonify({"ok": True})

# LIKED PAGE
@app.route("/liked")
def liked():
    cursor.execute("""
        SELECT track_name, artist_name 
        FROM user_history 
        WHERE username=%s AND action='like'
        ORDER BY id DESC
    """,(session["user"],))
    
    songs = cursor.fetchall()
    result = []

    for s in songs:
        img, preview = get_song_data(s[0], s[1])
        result.append({
            "name": s[0],
            "artist": s[1],
            "image": img,
            "preview": preview
        })

    return render_template("liked.html", songs=result)

if __name__ == "__main__":
    app.run(debug=True)
