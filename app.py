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

# ================== RECOMMEND ==================
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

# ================== SAVE HISTORY (FIXED DEBUG) ==================
def save_history(username, song_name, action):
    print("🔥 SAVE HISTORY CALLED:", username, song_name, action)

    row = data[data['track_name'].str.lower().str.contains(song_name.lower(), na=False)]
    if row.empty:
        print("❌ SONG NOT FOUND IN DATASET")
        return

    row = row.iloc[0]

    cursor.execute(
        "INSERT INTO user_history (username, track_name, artist_name, action) VALUES (%s,%s,%s,%s)",
        (username, row['track_name'], row['artist_name'], action)
    )
    db.commit()
    print("✅ SAVED TO DB")

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
        SELECT track_name FROM user_history
        WHERE username=%s AND action='play'
        ORDER BY id DESC LIMIT 5
    """, (username,))
    return [r[0] for r in cursor.fetchall()]

# ================== TRENDING ==================
def get_trending():
    cursor.execute("""
        SELECT track_name, COUNT(*) 
        FROM user_history
        GROUP BY track_name
        ORDER BY COUNT(*) DESC
        LIMIT 8
    """)
    return [r[0] for r in cursor.fetchall()]

# ================== AUTH ==================
@app.route('/login', methods=['GET','POST'])
def login():
    if request.method == 'POST':
        u = request.form['username']
        p = request.form['password']

        cursor.execute("SELECT * FROM users WHERE username=%s AND password=%s",(u,p))
        if cursor.fetchone():
            session['user'] = u
            return redirect('/')
        else:
            return "Invalid login"

    return render_template('login.html')

@app.route('/logout')
def logout():
    session.clear()
    return redirect('/login')

# ================== ACTION ==================
@app.route('/track_play', methods=['POST'])
def track_play():
    print("🔥 TRACK PLAY API HIT")

    user = session.get('user')
    data_req = request.get_json()

    print("USER:", user)
    print("DATA:", data_req)

    if user and data_req:
        save_history(user, data_req.get('song'), "play")

    return jsonify({"status": "ok"})

@app.route('/like', methods=['POST'])
def like():
    user = session.get('user')
    data_req = request.get_json()

    if user and data_req:
        save_history(user, data_req.get('song'), "like")

    return jsonify({"status": "ok"})

# ================== SEARCH ==================
@app.route('/search')
def search():
    q = request.args.get('q', '')
    res = data[data['track_name'].str.lower().str.contains(q.lower(), na=False)]
    return jsonify(res['track_name'].head(5).tolist())

# ================== HOME ==================
@app.route('/', methods=['GET','POST'])
def home():
    if 'user' not in session:
        return redirect('/login')

    user = session['user']

    recs = []
    if request.method == 'POST':
        recs = get_recommendations(request.form['song'])

    return render_template('index.html',
                           recommendations=recs,
                           history=get_user_history(user),
                           trending=get_trending(),
                           top_songs=data['track_name'].value_counts().head(10).index.tolist())

# ================== RUN ==================
if __name__ == '__main__':
    app.run(debug=True)
