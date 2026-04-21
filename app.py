from flask import Flask, render_template, request, jsonify, redirect, session
import pandas as pd
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity
import requests

app = Flask(__name__)
app.secret_key = "secret123"

# ===== DATA =====
data = pd.read_csv("tcc_ceds_music_sample.csv")
data.fillna("", inplace=True)

data["combined"] = data["genre"] + " " + data["artist_name"] + " " + data["track_name"]

tfidf = TfidfVectorizer(stop_words="english")
matrix = tfidf.fit_transform(data["combined"])
similarity = cosine_similarity(matrix)

# ===== TEMP STORAGE (NO DB NEEDED) =====
user_history = {}
user_likes = {}

# ===== FETCH IMAGE + PREVIEW =====
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

# ===== RECOMMENDER =====
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

# ===== HOME =====
@app.route("/", methods=["GET", "POST"])
def home():
    if "user" not in session:
        return redirect("/login")

    user = session["user"]

    recs = []
    if request.method == "POST":
        recs = recommend(request.form["song"])

    if not recs:
        recs = recommend("love")

    history = user_history.get(user, [])[-10:]

    # trending (simple global count)
    trending = []
    all_songs = []
    for u in user_history.values():
        all_songs.extend(u)

    seen = {}
    for s in all_songs:
        seen[s["name"]] = seen.get(s["name"], 0) + 1

    top = sorted(seen.items(), key=lambda x: x[1], reverse=True)[:10]

    for t in top:
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

    return render_template("index.html", recs=recs, history=history, trending=trending)

# ===== LOGIN =====
@app.route("/login", methods=["GET","POST"])
def login():
    if request.method == "POST":
        session["user"] = request.form["username"]
        user_history.setdefault(session["user"], [])
        user_likes.setdefault(session["user"], [])
        return redirect("/")
    return render_template("login.html")

# ===== LOGOUT =====
@app.route("/logout")
def logout():
    session.clear()
    return redirect("/login")

# ===== PLAY =====
@app.route("/play", methods=["POST"])
def play():
    data_req = request.get_json()
    user = session["user"]

    row = data[data["track_name"].str.lower().str.contains(data_req["song"].lower())]
    if not row.empty:
        row = row.iloc[0]
        img, preview = get_song_data(row["track_name"], row["artist_name"])

        user_history[user].append({
            "name": row["track_name"],
            "artist": row["artist_name"],
            "image": img,
            "preview": preview
        })

    return jsonify({"ok": True})

# ===== LIKE =====
@app.route("/like", methods=["POST"])
def like():
    data_req = request.get_json()
    user = session["user"]

    row = data[data["track_name"].str.lower().str.contains(data_req["song"].lower())]
    if not row.empty:
        row = row.iloc[0]
        img, preview = get_song_data(row["track_name"], row["artist_name"])

        user_likes[user].append({
            "name": row["track_name"],
            "artist": row["artist_name"],
            "image": img,
            "preview": preview
        })

    return jsonify({"ok": True})

# ===== LIKED PAGE =====
@app.route("/liked")
def liked():
    return render_template("liked.html", songs=user_likes.get(session["user"], []))

# ===== RUN =====
if __name__ == "__main__":
    app.run(debug=True)
