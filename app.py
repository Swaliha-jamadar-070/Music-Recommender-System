from flask import Flask, render_template, request, jsonify, redirect, session
import pandas as pd
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity
import requests
import mysql.connector

app = Flask(__name__)
app.secret_key = "secret123"

# ================== ✅ MYSQL CONNECTION ==================
db = mysql.connector.connect(
    host="localhost",
    user="root",
    password="",
    database="music_recommender"
)
cursor = db.cursor()

# ================== ✅ LOAD DATASET ==================
data = pd.read_csv('tcc_ceds_music_sample.csv')

for col in ['genre', 'artist_name', 'track_name', 'release_date']:
    data[col] = data[col].fillna('')

data['combined_features'] = data['genre'] + ' ' + data['artist_name'] + ' ' + data['track_name']

tfidf = TfidfVectorizer(stop_words='english')
tfidf_matrix = tfidf.fit_transform(data['combined_features'])
cosine_sim = cosine_similarity(tfidf_matrix, tfidf_matrix)

# ================== ✅ LOGIN ==================
USER = {"username": "admin", "password": "1234"}

# ================== 🎧 GET IMAGE ==================
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

# ================== 🎯 CONTENT BASED ==================
def get_recommendations(song_title):
    matches = data[data['track_name'].str.lower().str.contains(song_title.lower(), na=False)]

    if matches.empty:
        return []

    idx = matches.index[0]
    sim_scores = sorted(list(enumerate(cosine_sim[idx])), key=lambda x: x[1], reverse=True)[1:9]

    results = []
    for i, score in sim_scores:
        row = data.iloc[i]
        image, preview = get_song_data(row['track_name'], row['artist_name'])

        results.append({
            "name": row['track_name'],
            "artist": row['artist_name'],
            "genre": row['genre'],
            "year": row['release_date'],
            "image": image,
            "preview": preview,
            "score": round(score * 100, 2)
        })
    return results

# ================== ✅ SAVE HISTORY ==================
def save_history(username, song_name, action):
    try:
        row = data[data['track_name'] == song_name].iloc[0]

        cursor.execute(
            "INSERT INTO user_history (username, track_name, artist_name, action) VALUES (%s,%s,%s,%s)",
            (username, row['track_name'], row['artist_name'], action)
        )
        db.commit()
    except:
        pass

# ================== ✅ GET USER HISTORY ==================
def get_user_history(username):
    cursor.execute(
        "SELECT track_name FROM user_history WHERE username=%s",
        (username,)
    )
    return [row[0] for row in cursor.fetchall()]

# ================== ✅ PERSONALIZED ==================
def recommend_for_user(username):
    history = get_user_history(username)

    if not history:
        return []

    all_recommendations = []

    for song in history:
        recs = get_recommendations(song)
        all_recommendations.extend(recs)

    unique = {r['name']: r for r in all_recommendations}

    return list(unique.values())[:10]

# ================== 🔐 ROUTES ==================

@app.route('/login', methods=['GET', 'POST'])
def login():
    error = None
    if request.method == 'POST':
        if request.form['username'] == USER['username'] and request.form['password'] == USER['password']:
            session['user'] = request.form['username']
            return redirect('/')
        else:
            error = "Invalid username or password"
    return render_template('login.html', error=error)

@app.route('/logout')
def logout():
    session.pop('user', None)
    return redirect('/login')

# ❤️ LIKE
@app.route('/like', methods=['POST'])
def like():
    song = request.json.get('song')
    user = session.get('user')

    save_history(user, song, "like")

    return jsonify({"status": "liked"})

# ▶️ TRACK PLAY
@app.route('/track_play', methods=['POST'])
def track_play():
    song = request.json.get('song')
    user = session.get('user')

    save_history(user, song, "play")

    return jsonify({"status": "tracked"})

# 🔍 SEARCH
@app.route('/search')
def search():
    q = request.args.get('q', '')
    if not q:
        return jsonify([])
    res = data[data['track_name'].str.lower().str.contains(q.lower(), na=False)]
    return jsonify(res['track_name'].head(5).tolist())

# 🏠 HOME
@app.route('/', methods=['GET', 'POST'])
def home():
    if 'user' not in session:
        return redirect('/login')

    user = session['user']

    # ✅ Personalized
    recommendations = recommend_for_user(user)

    top_songs = data['track_name'].value_counts().head(12).index.tolist()

    # manual search override
    if request.method == 'POST':
        recommendations = get_recommendations(request.form['song'])

    return render_template('index.html',
                           recommendations=recommendations,
                           top_songs=top_songs)

# ================== 🚀 RUN ==================
if __name__ == '__main__':
    app.run(debug=True)
