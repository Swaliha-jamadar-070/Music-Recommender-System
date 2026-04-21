from flask import Flask, render_template, request, jsonify, redirect, session
import pandas as pd
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity
import requests
import mysql.connector
import os

app = Flask(__name__)
app.secret_key = "secret123"

# ================== MYSQL ==================
db = mysql.connector.connect(
    host="localhost",
    user="root",
    password="",
    database="music_recommender"
)
cursor = db.cursor()

# ================== LOAD DATA ==================
data = pd.read_csv('tcc_ceds_music_sample.csv')

for col in ['genre', 'artist_name', 'track_name', 'release_date']:
    data[col] = data[col].fillna('')

data['combined'] = data['genre'] + ' ' + data['artist_name'] + ' ' + data['track_name']

tfidf = TfidfVectorizer(stop_words='english')
tfidf_matrix = tfidf.fit_transform(data['combined'])
cosine_sim = cosine_similarity(tfidf_matrix, tfidf_matrix)

# ================== IMAGE ==================
def get_song_data(song, artist):
    try:
        url = f"https://itunes.apple.com/search?term={song} {artist}&limit=1"
        res = requests.get(url).json()
        if res['resultCount'] > 0:
            item = res['results'][0]
            return item['artworkUrl100'], item.get('previewUrl', "")
    except:
        pass
    return "https://via.placeholder.com/300", ""

# ================== CONTENT RECOMMEND ==================
def get_recommendations(song_title):
    matches = data[data['track_name'].str.lower().str.contains(song_title.lower(), na=False)]
    if matches.empty:
        return []

    idx = matches.index[0]
    scores = list(enumerate(cosine_sim[idx]))
    scores = sorted(scores, key=lambda x: x[1], reverse=True)[1:9]

    results = []
    for i, score in scores:
        row = data.iloc[i]
        image, preview = get_song_data(row['track_name'], row['artist_name'])

        results.append({
            "name": row['track_name'],
            "artist": row['artist_name'],
            "genre": row['genre'],
            "year": row['release_date'],
            "image": image,
            "preview": preview,
            "score": score * 100
        })
    return results

# ================== SAVE HISTORY ==================
def save_history(username, song_name, action):
    row = data[data['track_name'].str.lower().str.contains(song_name.lower(), na=False)]
    if row.empty:
        return

    row = row.iloc[0]

    cursor.execute(
        "INSERT INTO user_history (username, track_name, artist_name, action) VALUES (%s,%s,%s,%s)",
        (username, row['track_name'], row['artist_name'], action)
    )
    db.commit()

# ================== HISTORY ==================
def get_user_history(username):
    cursor.execute("""
        SELECT track_name, artist_name, action
        FROM user_history
        WHERE username=%s
        ORDER BY id DESC
        LIMIT 10
    """, (username,))
    return cursor.fetchall()

# ================== RECENT ==================
def get_recently_played(username):
    cursor.execute("""
        SELECT track_name, artist_name
        FROM user_history
        WHERE username=%s AND action='play'
        ORDER BY id DESC
        LIMIT 5
    """, (username,))
    return cursor.fetchall()

# ================== GENRE ==================
def get_user_favorite_genres(username):
    cursor.execute("""
        SELECT d.genre, COUNT(*) 
        FROM user_history uh
        JOIN tcc_ceds_music_sample d ON uh.track_name = d.track_name
        WHERE uh.username=%s
        GROUP BY d.genre
        ORDER BY COUNT(*) DESC
        LIMIT 3
    """, (username,))
    return [row[0] for row in cursor.fetchall()]

# ================== COLLAB ==================
def collaborative_recommend(username):
    cursor.execute("""
        SELECT DISTINCT username
        FROM user_history
        WHERE track_name IN (
            SELECT track_name FROM user_history WHERE username=%s
        ) AND username != %s
    """, (username, username))

    users = [u[0] for u in cursor.fetchall()]
    songs = []

    for u in users:
        cursor.execute("SELECT track_name FROM user_history WHERE username=%s AND action='like'", (u,))
        songs += [s[0] for s in cursor.fetchall()]

    return list(set(songs))[:10]

# ================== PERSONAL ==================
def recommend_for_user(username):
    history = get_user_history(username)
    if not history:
        return []

    fav_genres = get_user_favorite_genres(username)
    score_map = {}

    for song, artist, action in history:
        recs = get_recommendations(song)

        for r in recs:
            key = r['name']

            if key not in score_map:
                score_map[key] = r

            if action == "like":
                score_map[key]['score'] += 30
            elif action == "play":
                score_map[key]['score'] += 10

            if r['genre'] in fav_genres:
                score_map[key]['score'] += 15

    recommendations = list(score_map.values())

    # add collaborative
    for s in collaborative_recommend(username):
        recommendations.append({
            "name": s,
            "artist": "",
            "genre": "",
            "year": "",
            "image": "https://via.placeholder.com/300",
            "preview": "",
            "score": 50
        })

    return sorted(recommendations, key=lambda x: x['score'], reverse=True)[:10]

# ================== TRENDING ==================
def get_trending():
    cursor.execute("""
        SELECT track_name, COUNT(*) 
        FROM user_history
        GROUP BY track_name
        ORDER BY COUNT(*) DESC
        LIMIT 8
    """)
    return [row[0] for row in cursor.fetchall()]

# ================== AUTH ==================
@app.route('/register', methods=['GET', 'POST'])
def register():
    msg = None
    if request.method == 'POST':
        u = request.form['username']
        p = request.form['password']

        cursor.execute("SELECT * FROM users WHERE username=%s", (u,))
        if cursor.fetchone():
            msg = "User already exists"
        else:
            cursor.execute("INSERT INTO users (username,password) VALUES (%s,%s)", (u,p))
            db.commit()
            return redirect('/login')

    return render_template('register.html', msg=msg)

@app.route('/login', methods=['GET', 'POST'])
def login():
    error = None
    if request.method == 'POST':
        u = request.form['username']
        p = request.form['password']

        cursor.execute("SELECT * FROM users WHERE username=%s AND password=%s", (u,p))
        if cursor.fetchone():
            session['user'] = u
            return redirect('/')
        else:
            error = "Invalid credentials"

    return render_template('login.html', error=error)

@app.route('/logout')
def logout():
    session.clear()
    return redirect('/login')

# ================== ACTIONS ==================
@app.route('/like', methods=['POST'])
def like():
    user = session.get('user')
    data_req = request.get_json()
    if user:
        save_history(user, data_req.get('song'), "like")
    return jsonify({"status": "ok"})

@app.route('/track_play', methods=['POST'])
def track_play():
    user = session.get('user')
    data_req = request.get_json()
    if user:
        save_history(user, data_req.get('song'), "play")
    return jsonify({"status": "ok"})

# ================== SEARCH ==================
@app.route('/search')
def search():
    q = request.args.get('q', '')
    res = data[data['track_name'].str.lower().str.contains(q.lower(), na=False)]
    return jsonify(res['track_name'].head(5).tolist())

# ================== HOME ==================
@app.route('/', methods=['GET', 'POST'])
def home():
    if 'user' not in session:
        return redirect('/login')

    user = session['user']

    recs = recommend_for_user(user)
    recent = get_recently_played(user)
    history = get_user_history(user)
    trending = get_trending()
    top_songs = data['track_name'].value_counts().head(10).index.tolist()

    if request.method == 'POST':
        recs = get_recommendations(request.form['song'])

    return render_template('index.html',
                           recommendations=recs,
                           top_songs=top_songs,
                           recent=recent,
                           history=history,
                           trending=trending)

# ================== RUN ==================
if __name__ == '__main__':
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port, debug=True)
