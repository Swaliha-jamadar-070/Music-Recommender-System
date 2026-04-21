from flask import Flask, render_template, request, jsonify, redirect, session
import pandas as pd
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity
import psycopg2
import os
import spotipy
from spotipy.oauth2 import SpotifyClientCredentials

app = Flask(__name__)
app.secret_key = "secret123"

# ================= CONFIG =================
DATABASE_URL = os.getenv("DATABASE_URL")

sp = spotipy.Spotify(auth_manager=SpotifyClientCredentials(
    client_id="YOUR_SPOTIFY_CLIENT_ID",
    client_secret="YOUR_SPOTIFY_CLIENT_SECRET"
))

conn = psycopg2.connect(DATABASE_URL)
conn.autocommit = True
cursor = conn.cursor()

# ================= TABLES =================
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
data = pd.read_csv('tcc_ceds_music_sample.csv').fillna('')
data['combined'] = data['genre'] + " " + data['artist_name'] + " " + data['track_name']

tfidf = TfidfVectorizer(stop_words='english')
cosine_sim = cosine_similarity(tfidf.fit_transform(data['combined']))

# ================= SPOTIFY =================
def get_song_data(song, artist):
    try:
        results = sp.search(q=f"{song} {artist}", limit=1)
        track = results['tracks']['items'][0]
        return track['album']['images'][0]['url'], track['preview_url']
    except:
        return "https://via.placeholder.com/300", ""

# ================= RECOMMEND =================
def get_recommendations(song):
    matches = data[data['track_name'].str.lower().str.contains(song.lower())]
    if matches.empty:
        return []

    idx = matches.index[0]
    scores = list(enumerate(cosine_sim[idx]))
    scores = sorted(scores, key=lambda x: x[1], reverse=True)[1:9]

    results = []
    for i, _ in scores:
        row = data.iloc[i]
        img, preview = get_song_data(row['track_name'], row['artist_name'])

        results.append({
            "name": row['track_name'],
            "artist": row['artist_name'],
            "image": img,
            "preview": preview
        })

    return results

# ================= HISTORY =================
def save_history(user, song, action):
    row = data[data['track_name'].str.lower().str.contains(song.lower())]
    if row.empty:
        return
    row = row.iloc[0]

    cursor.execute("""
        INSERT INTO user_history (username, track_name, artist_name, action)
        VALUES (%s,%s,%s,%s)
    """, (user, row['track_name'], row['artist_name'], action))


def get_history(user):
    cursor.execute("""
        SELECT track_name, artist_name
        FROM user_history
        WHERE username=%s AND action='play'
        ORDER BY id DESC LIMIT 5
    """, (user,))
    return cursor.fetchall()


def get_trending():
    cursor.execute("""
        SELECT track_name, COUNT(*)
        FROM user_history
        GROUP BY track_name
        ORDER BY COUNT(*) DESC LIMIT 5
    """)
    return [x[0] for x in cursor.fetchall()]

# ================= AI =================
def collaborative_recommend(user):
    cursor.execute("""
        SELECT track_name FROM user_history
        WHERE username=%s AND action='like'
    """, (user,))
    user_likes = [x[0] for x in cursor.fetchall()]

    if not user_likes:
        return []

    cursor.execute("SELECT username, track_name FROM user_history WHERE action='like'")
    all_data = cursor.fetchall()

    similar_users = set()
    for u, song in all_data:
        if song in user_likes and u != user:
            similar_users.add(u)

    recs = set()
    for u in similar_users:
        cursor.execute("""
            SELECT track_name FROM user_history
            WHERE username=%s AND action='like'
        """, (u,))
        recs.update([x[0] for x in cursor.fetchall()])

    return list(recs - set(user_likes))[:5]

# ================= ROUTES =================
@app.route('/login', methods=['GET','POST'])
def login():
    if request.method == 'POST':
        session['user'] = request.form['username']
        return redirect('/')
    return render_template("login.html")


@app.route('/logout')
def logout():
    session.clear()
    return redirect('/login')


@app.route('/track_play', methods=['POST'])
def track_play():
    user = session.get('user')
    song = request.json.get('song')
    if user and song:
        save_history(user, song, "play")
    return jsonify({"ok":True})


@app.route('/like', methods=['POST'])
def like():
    user = session.get('user')
    song = request.json.get('song')
    if user and song:
        save_history(user, song, "like")
    return jsonify({"ok":True})


@app.route('/liked')
def liked():
    user = session.get('user')
    cursor.execute("""
        SELECT track_name, artist_name
        FROM user_history
        WHERE username=%s AND action='like'
        ORDER BY id DESC
    """, (user,))
    songs = cursor.fetchall()
    return render_template("liked.html", songs=songs)


@app.route('/', methods=['GET','POST'])
def home():
    if 'user' not in session:
        return redirect('/login')

    recs = []
    if request.method == 'POST':
        recs = get_recommendations(request.form['song'])

    return render_template("index.html",
                           recommendations=recs,
                           history=get_history(session['user']),
                           trending=get_trending(),
                           ai_recs=collaborative_recommend(session['user']))

if __name__ == "__main__":
    app.run(debug=True)
