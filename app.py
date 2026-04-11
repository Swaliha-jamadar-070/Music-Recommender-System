from flask import Flask, render_template, request, jsonify, redirect, session
import pandas as pd
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity
import requests

app = Flask(__name__)
app.secret_key = "secret123"

# ✅ Load dataset
data = pd.read_csv('tcc_ceds_music_sample.csv')

for col in ['genre', 'artist_name', 'track_name', 'release_date']:
    data[col] = data[col].fillna('')

data['combined_features'] = data['genre'] + ' ' + data['artist_name'] + ' ' + data['track_name']

tfidf = TfidfVectorizer(stop_words='english')
tfidf_matrix = tfidf.fit_transform(data['combined_features'])
cosine_sim = cosine_similarity(tfidf_matrix, tfidf_matrix)

# Dummy login
USER = {"username": "admin", "password": "1234"}

# 🎧 Get image + preview
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

# 🎯 Recommendation
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

# 🔐 Login
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

# Logout
@app.route('/logout')
def logout():
    session.pop('user', None)
    return redirect('/login')

# ❤️ Like
@app.route('/like', methods=['POST'])
def like():
    song = request.json.get('song')
    if 'likes' not in session:
        session['likes'] = []
    session['likes'].append(song)
    session.modified = True
    return jsonify({"status": "liked"})

# 🔍 Search
@app.route('/search')
def search():
    q = request.args.get('q', '')
    if not q:
        return jsonify([])
    res = data[data['track_name'].str.lower().str.contains(q.lower(), na=False)]
    return jsonify(res['track_name'].head(5).tolist())

# 🏠 Home
@app.route('/', methods=['GET', 'POST'])
def home():
    if 'user' not in session:
        return redirect('/login')

    recommendations = []
    top_songs = data['track_name'].value_counts().head(5).index.tolist()

    if request.method == 'POST':
        recommendations = get_recommendations(request.form['song'])

    return render_template('index.html',
                           recommendations=recommendations,
                           top_songs=top_songs)

if __name__ == '__main__':
    app.run(debug=True)
    app.run(host="0.0.0.0", port=port)
