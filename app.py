from flask import Flask, render_template, request, jsonify, redirect, session
import pandas as pd
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity
import requests
import mysql.connector

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

data['combined_features'] = data['genre'] + ' ' + data['artist_name'] + ' ' + data['track_name']

tfidf = TfidfVectorizer(stop_words='english')
tfidf_matrix = tfidf.fit_transform(data['combined_features'])
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

# ================== SAVE HISTORY ==================
def save_history(username, song_name, action):
    print("👉 Saving:", username, song_name)

    row = data[data['track_name'].str.lower().str.contains(song_name.lower(), na=False)]

    if row.empty:
        print("❌ Song not found")
        return

    row = row.iloc[0]

    cursor.execute(
        "INSERT INTO user_history (username, track_name, artist_name, action) VALUES (%s,%s,%s,%s)",
        (username, row['track_name'], row['artist_name'], action)
    )

    db.commit()
    print("✅ Inserted into DB")

# ================== USER HISTORY ==================
def get_user_history(username):
    cursor.execute(
        "SELECT track_name, action FROM user_history WHERE username=%s ORDER BY id DESC LIMIT 10",
        (username,)
    )
    return cursor.fetchall()

# ================== PERSONALIZED ==================
def recommend_for_user(username):
    history = get_user_history(username)

    if not history:
        return []

    recommendations = []
    seen = set()

    for song, action in history:
        recs = get_recommendations(song)

        for r in recs:
            if r['name'] in seen:
                continue

            # 🔥 Smart scoring
            if action == "like":
                r['score'] += 20
            elif action == "play":
                r['score'] += 10

            seen.add(r['name'])
            recommendations.append(r)

    recommendations = sorted(recommendations, key=lambda x: x['score'], reverse=True)

    return recommendations[:10]

# ================== RECENT ==================
def get_recently_played(username):
    cursor.execute(
        "SELECT track_name FROM user_history WHERE username=%s ORDER BY id DESC LIMIT 5",
        (username,)
    )
    return [row[0] for row in cursor.fetchall()]

# ================== TRENDING ==================
def get_trending():
    cursor.execute("""
        SELECT track_name, COUNT(*) as count 
        FROM user_history 
        GROUP BY track_name 
        ORDER BY count DESC 
        LIMIT 8
    """)
    return [row[0] for row in cursor.fetchall()]

# ================== REGISTER ==================
@app.route('/register', methods=['GET', 'POST'])
def register():
    msg = None

    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']

        cursor.execute("SELECT * FROM users WHERE username=%s", (username,))
        if cursor.fetchone():
            msg = "User already exists"
        else:
            cursor.execute("INSERT INTO users (username,password) VALUES (%s,%s)", (username,password))
            db.commit()
            return redirect('/login')

    return render_template('register.html', msg=msg)

# ================== LOGIN ==================
@app.route('/login', methods=['GET', 'POST'])
def login():
    error = None

    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']

        cursor.execute("SELECT * FROM users WHERE username=%s AND password=%s", (username,password))
        user = cursor.fetchone()

        if user:
            session['user'] = username
            session.permanent = True
            return redirect('/')
        else:
            error = "Invalid credentials"

    return render_template('login.html', error=error)

# ================== LOGOUT ==================
@app.route('/logout')
def logout():
    session.clear()
    return redirect('/login')

# ================== LIKE ==================
@app.route('/like', methods=['POST'])
def like():
    user = session.get('user')
    data_req = request.get_json()

    if user and data_req:
        save_history(user, data_req.get('song'), "like")

    return jsonify({"status":"ok"})

# ================== TRACK PLAY ==================
@app.route('/track_play', methods=['POST'])
def track_play():
    print("🔥 track_play called")

    user = session.get('user')
    data_req = request.get_json()

    print("User:", user)
    print("Data:", data_req)

    if user and data_req:
        save_history(user, data_req.get('song'), "play")

    return jsonify({"status":"ok"})

# ================== SEARCH ==================
@app.route('/search')
def search():
    q = request.args.get('q', '')
    if not q:
        return jsonify([])

    res = data[data['track_name'].str.lower().str.contains(q.lower(), na=False)]
    return jsonify(res['track_name'].head(5).tolist())

# ================== HOME ==================
@app.route('/', methods=['GET', 'POST'])
def home():
    if 'user' not in session:
        return redirect('/login')

    user = session['user']

    recommendations = recommend_for_user(user)
    recent = get_recently_played(user)
    trending = get_trending()
    top_songs = data['track_name'].value_counts().head(10).index.tolist()

    if request.method == 'POST':
        recommendations = get_recommendations(request.form['song'])

    return render_template('index.html',
                           recommendations=recommendations,
                           top_songs=top_songs,
                           recent=recent,
                           trending=trending)

# ================== RUN ==================
if __name__ == '__main__':
    app.run(debug=True)
