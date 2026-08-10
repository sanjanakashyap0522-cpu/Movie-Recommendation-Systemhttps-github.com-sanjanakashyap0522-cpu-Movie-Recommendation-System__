import streamlit as st
import pickle
import pandas as pd
import requests
import os
import time
import gzip

with open('movies_dict.pkl', 'rb') as f:
    movies_dict = pickle.load(f)
from sklearn.feature_extraction.text import CountVectorizer
from sklearn.metrics.pairwise import cosine_similarity

# movies_dict.pkl load karo
with open("movies_dict.pkl", "rb") as f:
    movies_dict = pickle.load(f)
movies = pd.DataFrame(movies_dict)

# agar compressed similarity file missing hai to generate karo
if not os.path.exists("similarity.pkl.gz"):
    cv = CountVectorizer(max_features=5000, stop_words='english')
    vectors = cv.fit_transform(movies['title']).toarray()
    similarity = cosine_similarity(vectors).astype('float32')  # float32 se size half ho jaata hai

    # compressed file save karo
    with gzip.open("similarity.pkl.gz", "wb") as f:
        pickle.dump(similarity, f)

# hamesha compressed file load karo
with gzip.open("similarity.pkl.gz", "rb") as f:
    similarity = pickle.load(f)

movies = pd.DataFrame(movies_dict)

API_KEY = os.getenv("TMDB_API_KEY", "cefcd89e55f171fdc2e56c0c6900ee69")

CACHE_DIR = "poster_cache"
os.makedirs(CACHE_DIR, exist_ok=True)

@st.cache_data
def fetch_movie_details(movie_id, retries=3):
    cache_path = os.path.join(CACHE_DIR, f"{movie_id}.jpg")
    url = f"https://api.themoviedb.org/3/movie/{movie_id}?api_key={API_KEY}&language=en-US&append_to_response=videos"

    for attempt in range(retries):
        try:
            response = requests.get(url, timeout=25)
            response.raise_for_status()
            data = response.json()

            poster_path = data.get("poster_path")
            if poster_path:
                poster_url = f"https://image.tmdb.org/t/p/w500{poster_path}"
                if not os.path.exists(cache_path):
                    img_data = requests.get(poster_url, timeout=25).content
                    with open(cache_path, "wb") as f:
                        f.write(img_data)
                poster = cache_path
            else:
                poster = "https://via.placeholder.com/500x750?text=No+Poster"

            release_date = data.get("release_date", "")
            year = release_date.split("-")[0] if release_date else "N/A"
            rating = data.get("vote_average", "N/A")
            overview = data.get("overview", "No description available.")
            genres = [g["name"] for g in data.get("genres", [])]

            videos = data.get("videos", {}).get("results", [])
            trailer_url = None
            for v in videos:
                if v["type"] == "Trailer" and v["site"] == "YouTube":
                    trailer_url = f"https://www.youtube.com/watch?v={v['key']}"
                    break

            return {"poster": poster, "year": year, "rating": rating, "overview": overview, "genres": genres,
                    "trailer": trailer_url}
        except:
            time.sleep(2)

    return {
        "poster": "https://via.placeholder.com/500x750?text=Error",
        "year": "N/A",
        "rating": "N/A",
        "overview": "Error fetching details.",
        "genres": [],
        "trailer": None
    }

def recommend(movie):
    try:
        movie_index = movies[movies['title'] == movie].index[0]
    except IndexError:
        return []

    distances = similarity[movie_index]
    movies_list = sorted(list(enumerate(distances)), reverse=True, key=lambda x: x[1])[1:6]

    recommendations = []
    for i in movies_list:
        movie_data = movies.iloc[i[0]]
        movie_id = movie_data.get('movie_id', None)
        if movie_id:
            details = fetch_movie_details(movie_id)
            recommendations.append({
                "title": movie_data['title'],
                "poster": details["poster"],
                "year": details["year"],
                "rating": details["rating"],
                "overview": details["overview"],
                "genres": details["genres"],
                "trailer": details["trailer"]
            })
        else:
            recommendations.append({
                "title": movie_data['title'],
                "poster": "https://via.placeholder.com/500x750?text=No+Poster",
                "year": "N/A",
                "rating": "N/A",
                "overview": "No description available.",
                "genres": [],
                "trailer": None
            })
        time.sleep(0.5)

    return recommendations
st.set_page_config(page_title="Movie Recommender", layout="wide")

# ---------------- Helper Functions ----------------
def format_movies(data):
    movies = []
    for m in data:
        movies.append({
            "title": m.get("title"),
            "year": m.get("release_date", "N/A")[:4],
            "rating": m.get("vote_average", "N/A"),
            "overview": m.get("overview", ""),
            "poster": f"https://image.tmdb.org/t/p/w500{m['poster_path']}" if m.get("poster_path") else None
        })
    return movies

def search_movies(query):
    url = f"https://api.themoviedb.org/3/search/movie?api_key=cefcd89e55f171fdc2e56c0c6900ee69&query={query}"
    response = requests.get(url, timeout=15)
    if response.status_code == 200:
        data = response.json()["results"]
        return format_movies(data)
    return []
def get_movies_by_genre(genre_name, retries=3, delay=2):
    genre_map = {
        "Action": 28, "Comedy": 35, "Drama": 18,
        "Horror": 27, "Romance": 10749
    }
    genre_id = genre_map.get(genre_name)
    if not genre_id:
        return []

    url = f"https://api.themoviedb.org/3/discover/movie?api_key={"cefcd89e55f171fdc2e56c0c6900ee69"}&with_genres={genre_id}"

    for attempt in range(retries):
        try:
            response = requests.get(url, timeout=15)
            response.raise_for_status()
            data = response.json()["results"]
            return format_movies(data)
        except requests.exceptions.RequestException as e:
            if attempt < retries - 1:
                time.sleep(delay)  # wait before retry
            else:
                st.error(f"⚠️ Failed to fetch genre movies: {e}")
                return []


def get_trending_movies():
    url = f"https://api.themoviedb.org/3/trending/movie/week?api_key={"cefcd89e55f171fdc2e56c0c6900ee69"}"
    response = requests.get(url)
    if response.status_code == 200:
        data = response.json()["results"]
        return format_movies(data)
    return []

def get_top_rated_movies():
    url = f"https://api.themoviedb.org/3/movie/top_rated?api_key={"cefcd89e55f171fdc2e56c0c6900ee69"}"
    response = requests.get(url)
    if response.status_code == 200:
        data = response.json()["results"]
        return format_movies(data)
    return []

def format_movies(data):
    movies = []
    for m in data:
        movies.append({
            "title": m.get("title"),
            "year": m.get("release_date", "N/A")[:4],
            "rating": m.get("vote_average", "N/A"),
            "overview": m.get("overview", ""),
            "poster": f"https://image.tmdb.org/t/p/w500{m['poster_path']}" if m.get("poster_path") else None
        })
    return movies

# 🎨 Background Image CSS + Button Colors
background_image_url = "https://wallpaperaccess.com/full/3295830.jpg"
st.markdown(
    f"""
    <style>
    .stApp {{
        background-image: url("{background_image_url}");
        background-size: cover;
        background-attachment: fixed;
        background-position: center;
    }}
    .stMarkdown, .stText, .stTitle, .stHeader, .stSubheader {{
        background-color: rgba(0,0,0,0.6);
        color: white;
        padding: 10px;
        border-radius: 8px;
    }}
    /* 🎯 Recommend button yellow */
    div[data-testid="stButton"] > button:first-child {{
        background-color: #FFFF00;
        color: black;
        font-size: 24px;      /* 👈 text size bada */
        font-weight: bold;    /* 👈 text mota */
        padding: 12px 30px;   /* 👈 button size bhi bada */
    }}
    /* 💬 Submit Feedback button yellow */
    div[data-testid="stButton"] > button:nth-child(2) {{
        background-color: #FFFF00;
        color: black;
        font-size: 22px;      /* 👈 text size bada */
        font-weight: bold;
        padding: 10px 25px;
    }}
    .black-box {{
        background-color: black;
        color: white;
        padding: 20px;
        border-radius: 10px;
        margin-bottom: 20px;
    }}
    </style>
    """,
    unsafe_allow_html=True
)

# Favorites state
if "favorites" not in st.session_state:
    st.session_state["favorites"] = []

# Sidebar options
page = st.sidebar.radio(
    "📃 Pages",
    ["🏠Home", "🔍 Search Movies", "🎯 Recommend Movies", "🎭 Explore by Genre", "🔥 Trending", "⭐ Top Rated","❤️ Favourites"]
)
# ---------------- HOME ----------------
if page == "🏠Home":
    st.markdown(
        """
        <h1 style="
            font-size: 80px;
            font-weight: bold;
            color: white;
            text-align: center;
            text-shadow: 0px 0px 15px #ffffff, 0px 0px 30px #FFD700;
        ">
        🎬 Movie Recommendation System
        </h1>
        """,
        unsafe_allow_html=True
    )
    st.markdown(
        """
        <div style="
            background-color:0;
            color: white;
            font-weight: bold; 
            padding: 10px;
            border-radius: 2px;
            box-shadow: 2px 2px 8px rgba(0,0,0,0.8);
            margin-bottom: 2px;
        ">
            <h4>✨ _Select a one movie and get five recommendations!_</h4>
        </div>
        """,
        unsafe_allow_html=True
    )

    st.title("🎯 Recommend Movies")
    selected_movie_name = st.selectbox("🎥_Your Next Favorite Movie Is Just One Search Away_✌️🍿", movies['title'].values)
    st.markdown(
        """
        <style>
        /* 🎨 Selectbox label white */
        div[data-baseweb="select"] label {
            color: white !important;
            font-weight: bold;
            font-size: 18px;
        }
        </style>
        """,
        unsafe_allow_html=True
    )

    # Custom CSS for Recommend button
    st.markdown(
        """
        <style>
        div[data-testid="stButton"] > button:first-child {
            font-size: 28px !important;
            font-weight: 900;
            padding: 15px 40px !important;
            height: 65px !important;
            width: 280px !important;
            border-radius: 12px;
            background: linear-gradient(45deg, #FFD700, #FFA500);
            color: black;
            box-shadow: 0px 4px 12px rgba(0,0,0,0.5);
            transition: transform 0.2s;
        }
        div[data-testid="stButton"] > button:first-child:hover {
            transform: scale(1.05);
            background: linear-gradient(45deg, #FFA500, #FFD700);
        }
        </style>
        """,
        unsafe_allow_html=True
    )

    if st.button("Get Recommendations"):
        recs = recommend(selected_movie_name)
        if len(recs) == 0:
            st.error("Movie not found")
        else:
            st.session_state["recs"] = recs

    if "recs" in st.session_state:
        for rec in st.session_state["recs"]:
            st.markdown("---")
            cols = st.columns([1,2])
            with cols[0]:
                if rec["poster"].endswith(".jpg"):
                    with open(rec["poster"], "rb") as f:
                        st.image(f.read(), width=800)
                else:
                    st.image(rec["poster"], width=800)
            with cols[1]:
                st.markdown(f"**🎬 Title:** {rec['title']}")
                st.markdown(f"**📅 Year:** {rec['year']}")
                st.markdown(f"**⭐ Rating:** {rec['rating']}")
                st.markdown("**🎭 Genres:** " + ", ".join(rec["genres"]) if rec["genres"] else "🎭 Genres: N/A")
                st.markdown(f"**📖 Overview:** {rec['overview'][:150]}...")
                if st.button(f"Show More about {rec['title']}", key=f"show_{rec['title']}"):
                    st.info(rec["overview"])
                if rec["trailer"]:
                    st.markdown(f"[▶ Watch Trailer]({rec['trailer']})")
                if st.button(f"❤️ Add {rec['title']} to Favorites", key=f"fav_{rec['title']}"):
                    st.session_state["favorites"].append(rec)
                    st.success(f"{rec['title']} added to favorites!")
    st.title("🔍 Search Movies")
    query = st.text_input("Enter movie name:")
    st.markdown(
        """
        <style>
        /* 🔍 Text input label white */
        div[data-baseweb="input"] label {
            color: white !important;
            font-weight: bold;
            font-size: 18px;
        }
        </style>
        """,
        unsafe_allow_html=True
    )

    if query:
        results = search_movies(query)
        if results:
            for movie in results:
                st.markdown("---")
                if movie["poster"]:
                    st.image(movie["poster"], width=200)
                st.write(f"🎬 {movie['title']} ({movie['year']}) ⭐ {movie['rating']}")
                st.write(f"📖 {movie['overview'][:150]}...")
        else:
            st.warning("No movies found!")
    st.title("🎭 Explore by Genre")
    genre = st.selectbox("Choose a genre:", ["Select Genre", "Action", "Comedy", "Drama", "Horror", "Romance"])
    st.markdown(
        """
        <style>
        /* 🎭 Selectbox label white */
        div[data-baseweb="select"] label {
            color: white !important;
            font-weight: bold;
            font-size: 18px;
        }
        </style>
        """,
        unsafe_allow_html=True
    )

    # Show movies only when user clicks button
    if genre != "Select Genre":
        if st.button("Show Movies"):
            genre_movies = get_movies_by_genre(genre)
            if genre_movies:
                for movie in genre_movies:
                    st.markdown("---")
                    if movie["poster"]:
                        st.image(movie["poster"], width=200)
                    st.write(f"🎬 {movie['title']} ({movie['year']}) ⭐ {movie['rating']}")
                    st.write(f"📖 {movie['overview'][:150]}...")
            else:
                st.warning("No movies found for this genre!")
    else:
        st.info("👉 Please select a genre to explore movies.")
    st.title("🔥 Trending Movies")

    # Button to control when movies appear
    if st.button("Show Trending Movies"):
        trending = get_trending_movies()
        if trending:
            for movie in trending:
                st.markdown("---")
                if movie["poster"]:
                    st.image(movie["poster"], width=200)
                st.write(f"🎬 {movie['title']} ({movie['year']}) ⭐ {movie['rating']}")
                st.write(f"📖 {movie['overview'][:150]}...")
        else:
            st.warning("No trending movies found!")
    else:
        st.info("👉 Click the button above to see trending movies.")
    st.title("⭐ Top Rated Movies")
    # Button to control when movies appear
    if st.button("Show Top Rated Movies"):
        top_rated = get_top_rated_movies()
        if top_rated:
            for movie in top_rated:
                st.markdown("---")
                if movie["poster"]:
                    st.image(movie["poster"], width=200)
                st.write(f"🎬 {movie['title']} ({movie['year']}) ⭐ {movie['rating']}")
                st.write(f"📖 {movie['overview'][:150]}...")
        else:
            st.warning("No top rated movies found!")
    else:
        st.info("👉 Click the button above to see top rated movies.")

    st.title("❤️ Your Favourite Movies")

    # 🎨 Cinematic styled motivational comment box
    st.markdown(
        """
        <div style="
            background: linear-gradient(45deg, #FFD700, #FF8C00);
            color: black;
            font-weight: bold;
            font-size: 20px;
            text-align: center;
            padding: 18px;
            border-radius: 15px;
            box-shadow: 0px 0px 20px rgba(0,0,0,0.9);
            margin-bottom: 25px;
            font-family: 'Georgia', serif;
            text-shadow: 1px 1px 5px #fff;
        ">
        🍿✨ *"A favorite movie is not just a film — it's a memory, a mood, and a magical journey.  
        Add your favorites today and let every story stay with you forever!"* 🎬❤️
        </div>
        """,
        unsafe_allow_html=True
    )

    if len(st.session_state["favorites"]) == 0:
        st.info("No favorites yet. Add some favourite movies from Home page!")
    else:
        fav_titles = [fav['title'] for fav in st.session_state["favorites"]]
        selected_fav = st.selectbox("Choose a movie to view details:", fav_titles, key="favorites_dropdown")

        if selected_fav is not None:
            fav_movie = next(f for f in st.session_state["favorites"] if f['title'] == selected_fav)
            st.markdown("---")
            if fav_movie["poster"]:
                st.image(fav_movie["poster"], width=300)
            st.markdown(f"**🎬 Title:** {fav_movie['title']}")
            st.markdown(f"**📅 Year:** {fav_movie['year']}")
            st.markdown(f"**⭐ Rating:** {fav_movie['rating']}")
            st.markdown(f"**📖 Overview:** {fav_movie['overview'][:150]}...")

    st.title("🤞Your Feedback")

    st.markdown(
        """
        <div style="
            background-color:0;
            color: white;
            font-weight: bold; 
            padding: 10px;
            border-radius: 2px;
            box-shadow: 2px 2px 8px rgba(0,0,0,0.8);
            margin-bottom: 2px;
        ">
            <h4>Rate the recommendations:-</h4>
        </div>
        """,
        unsafe_allow_html=True
    )

    sentiment_mapping = ["one", "two", "three", "four", "five"]
    selected = st.feedback("stars")
    if selected is not None:
        st.markdown(f"You selected {sentiment_mapping[selected]} star(s).")

    st.markdown(
        """
        <div style="
            background-color:0;
            color: white;
            font-weight: bold; 
            padding: 10px;
            border-radius: 2px;
            box-shadow: 2px 2px 8px rgba(0,0,0,0.8);
            margin-bottom: 2px;
        ">
            <h4>Did you like the recommendations?</h4>
        </div>
        """,
        unsafe_allow_html=True
    )

    thumb = st.radio("", ["👍 Yes", "👎 No"])
    st.write(f"You selected: {thumb}")
    st.markdown(
        """
        <style>
        /* ⭐ Feedback stars text white + bigger */
        .stMarkdown {
            color: white !important;
            font-size: 952px !important;
            font-weight: bold;
        }

        /* 👍👎 Radio button labels white + bigger */
        div[role="radiogroup"] label {
            color: white !important;
            font-size: 900px !important;
            font-weight: bold;
        }
        </style>
        """,
        unsafe_allow_html=True
    )

    st.title("💬 Share your thoughts:-")
    comment = st.text_area("", key="feedback_box", label_visibility="collapsed")

    # ✅ Condition: Only allow submit if comment is not empty
    if st.button("Submit Feedback"):
        if comment.strip() == "":
            st.warning("⚠️ Please write a comment before submitting.")
        else:
            st.markdown(
                """
                <div style="
                    background-color: #FFFFE0; 
                    color: black;
                    font-weight: bold;
                    padding: 2px;
                    border-radius: 5px;
                    margin-top: 1px;
                ">
                “_Thanks for sharing your thoughts! Keep discovering, keep enjoying movies. We truly appreciate your feedback!_” ♥️
                </div>
                """,
                unsafe_allow_html=True
            )


# ---------------- RECOMMEND MOVIES ----------------
elif page == "🎯 Recommend Movies":
    st.title("🎯 Recommend Movies")
    selected_movie = st.selectbox(":", movies['title'].values)
    if st.button("Get Recommendations"):
        recs = recommend(selected_movie)   # <-- apna recommend function call karo
        for rec in recs:
            st.write(f"🎬 {rec['title']} ({rec['year']}) ⭐ {rec['rating']}")

# ---------------- SEARCH MOVIES ----------------
if page == "🔍 Search Movies":
    st.title("🔍 Search Movies")
    query = st.text_input("Enter movie name:")
    if query:
        results = search_movies(query)
        if results:
            for movie in results:
                st.markdown("---")
                if movie["poster"]:
                    st.image(movie["poster"], width=200)
                st.write(f"🎬 {movie['title']} ({movie['year']}) ⭐ {movie['rating']}")
                st.write(f"📖 {movie['overview'][:150]}...")
        else:
            st.warning("No movies found!")

# ---------------- GENRE ----------------
elif page == "🎭 Explore by Genre":
    st.title("🎭 Explore by Genre")
    genre = st.selectbox("Choose a genre:", ["Action", "Comedy", "Drama", "Horror", "Romance"])
    if genre:
        genre_movies = get_movies_by_genre(genre)
        for movie in genre_movies:
            st.markdown("---")
            if movie["poster"]:
                st.image(movie["poster"], width=200)
            st.write(f"🎬 {movie['title']} ({movie['year']}) ⭐ {movie['rating']}")
            st.write(f"📖 {movie['overview'][:150]}...")

# ---------------- TRENDING ----------------
elif page == "🔥 Trending":
    st.title("🔥 Trending Movies")
    trending = get_trending_movies()
    for movie in trending:
        st.markdown("---")
        if movie["poster"]:
            st.image(movie["poster"], width=200)
        st.write(f"🎬 {movie['title']} ({movie['year']}) ⭐ {movie['rating']}")
        st.write(f"📖 {movie['overview'][:150]}...")

# ---------------- TOP RATED ----------------
elif page == "⭐ Top Rated":
    st.title("⭐ Top Rated Movies")
    top_rated = get_top_rated_movies()
    for movie in top_rated:
        st.markdown("---")
        if movie["poster"]:
            st.image(movie["poster"], width=200)
        st.write(f"🎬 {movie['title']} ({movie['year']}) ⭐ {movie['rating']}")
        st.write(f"📖 {movie['overview'][:150]}...")
# ---------------- FAVORITES PAGE ----------------
elif page == "❤️ Favourites":
    st.title("❤️ Your Favourite Movies")
# 🎨 Cinematic styled motivational comment box
    st.markdown(
        """
        <div style="
            background: linear-gradient(45deg, #FFD700, #FF8C00);
            color: black;
            font-weight: bold;
            font-size: 20px;
            text-align: center;
            padding: 18px;
            border-radius: 15px;
            box-shadow: 0px 0px 20px rgba(0,0,0,0.9);
            margin-bottom: 25px;
            font-family: 'Georgia', serif;
            text-shadow: 1px 1px 5px #fff;
        ">
        🍿✨ *"A favorite movie is not just a film — it's a memory, a mood, and a magical journey.  
        Add your favorites today and let every story stay with you forever!"* 🎬❤️
        </div>
        """,
        unsafe_allow_html=True
    )

    if len(st.session_state["favorites"]) == 0:
        st.info("No favorites yet. Add some favourite movies from Home page!")
    else:
        fav_titles = [fav['title'] for fav in st.session_state["favorites"]]
        selected_fav = st.selectbox("Choose a movie to view details:", fav_titles, key="favorites_dropdown")

        if selected_fav is not None:
            fav_movie = next(f for f in st.session_state["favorites"] if f['title'] == selected_fav)
            st.markdown("---")
            if fav_movie["poster"]:
                st.image(fav_movie["poster"], width=300)
            st.markdown(f"**🎬 Title:** {fav_movie['title']}")
            st.markdown(f"**📅 Year:** {fav_movie['year']}")
            st.markdown(f"**⭐ Rating:** {fav_movie['rating']}")
            st.markdown(f"**📖 Overview:** {fav_movie['overview'][:150]}...")
# ---------------- SIDEBAR FEEDBACK ----------------
    st.sidebar.title("🤞 Your Feedback")

sentiment_mapping = ["one", "two", "three", "four", "five"]

# ⭐ Star rating feedback
selected_sidebar = st.sidebar.feedback("stars")
if selected_sidebar is not None:
    st.sidebar.write(f"You selected {sentiment_mapping[selected_sidebar]} star(s).")

# 👍👎 Like/Dislike feedback
thumb_sidebar = st.sidebar.radio("Did you like the recommendations?", ["👍 Yes", "👎 No"])
st.sidebar.write(f"You selected: {thumb_sidebar}")

# 💬 Text feedback
comment_sidebar = st.sidebar.text_area("💬 Share your thoughts:", key="sidebar_feedback_box")

# ✅ Condition: Only allow submit if comment is not empty
if st.sidebar.button("Submit Feedback"):
    if comment_sidebar.strip() == "":
        st.sidebar.warning("⚠️ Please write a comment before submitting.")
    else:
        st.sidebar.success(" “_Thanks for sharing your thoughts! Keep discovering, keep enjoying movies. We truly appreciate your feedback!_” ♥️")

st.markdown(
    """
    <style>
    /* 🎨 Make all headings/titles white, bold and stylish */
    h1, h2, h3, h4, h5, h6 {
        color: white !important;
        font-weight: 900 !important;   /* Motte akshar (extra bold) */
        font-family: 'Georgia', serif; /* Stylish font */
        text-shadow: 1px 1px 5px #000; /* Thoda shadow for style */
    }
    .stTitle, .stHeader, .stSubheader {
        color: white !important;
        font-weight: 900 !important;
        font-family: 'Georgia', serif;
        text-shadow: 1px 1px 5px #000;
    }
    </style>
    """,
    unsafe_allow_html=True
)



# 🎬 Background image
background_image_url = "https://copilot.microsoft.com/th/id/BCO.e5c6b42f-ae27-4177-9a0f-a7011533f7d0.png"
st.markdown(
    f"""
    <style>
    .stApp {{
        background-image: url("{background_image_url}");
        background-size: cover;
                background-attachment: fixed;
        background-position: center;
    }}
    .movie-card {{
        background-color: rgba(0,0,0,0.8);
        border-radius: 10px;
        padding: 10px;
        text-align: center;
        color: white;
        box-shadow: 0 0 15px #FFD700;
        transition: transform 0.3s;
        margin: 10px;
    }}
    .movie-card:hover {{
        transform: scale(1.05);
    }}
    </style>
    """,
    unsafe_allow_html=True
)

# 🎞️ Movie data
movies = [
    {
        "title": "Avatar",
        "poster": "https://image.tmdb.org/t/p/w500/jRXYjXNq0Cs2TcJjLkki24MLp7u.jpg",
        "year": 2009,
        "rating": 7.8,
        "overview": "A paraplegic Marine dispatched to the moon Pandora on a unique mission becomes torn between following orders and protecting an alien civilization."
    },
    {
        "title": "Avengers: Endgame",
        "poster": "https://image.tmdb.org/t/p/w500/ulzhLuWrPK07P1YkdWQLZnQh1JL.jpg",
        "year": 2019,
        "rating": 8.4,
        "overview": "After the devastating events of Infinity War, the Avengers assemble once more to reverse Thanos' actions and restore balance to the universe."
    },
    {
        "title": "Spider-Man: No Way Home",
        "poster": "https://image.tmdb.org/t/p/w500/1g0dhYtq4irTY1GPXvft6k4YLjm.jpg",
        "year": 2021,
        "rating": 8.2,
        "overview": "Peter Parker seeks Doctor Strange's help to restore his secret identity, but the spell goes wrong, unleashing villains from other universes."
    },
    {
        "title": "Iron Man",
        "poster": "https://image.tmdb.org/t/p/w500/78lPtwv72eTNqFW9COBYI0dWDJa.jpg",
        "year": 2008,
        "rating": 7.9,
        "overview": "After being held captive, billionaire engineer Tony Stark builds a high-tech suit of armor to fight evil and becomes Iron Man."
    },
    {
        "title": "Titanic",
        "poster": "https://image.tmdb.org/t/p/w500/9xjZS2rlVxm8SFx8kPC3aIGCOYQ.jpg",
        "year": 1997,
        "rating": 7.9,
        "overview": "A young couple from different social classes fall in love aboard the ill-fated RMS Titanic."
    },
    {
        "title": "The Matrix",
        "poster": "https://image.tmdb.org/t/p/w500/f89U3ADr1oiB1s9GkdPOEpXUk5H.jpg",
        "year": 1999,
        "rating": 8.7,
        "overview": "A computer hacker learns about the true nature of reality and his role in the war against its controllers."
    },
    {
        "title": "The Dark Knight",
        "poster": "https://image.tmdb.org/t/p/w500/qJ2tW6WMUDux911r6m7haRef0WH.jpg",
        "year": 2008,
        "rating": 9.0,
        "overview": "Batman faces the Joker, a criminal mastermind who plunges Gotham into chaos."
    },
    {
        "title": "Dunkirk",
        "poster": "https://image.tmdb.org/t/p/w500/ebSnODDg9lbsMIaWg2uAbjn7TO5.jpg",
        "year": 2017,
        "rating": 7.8,
        "overview": "Allied soldiers from Belgium, the British Empire, and France are surrounded by the German Army and evacuated during a fierce battle in World War II."
    },
    {
        "title": "The Shawshank Redemption",
        "poster": "https://image.tmdb.org/t/p/w500/q6y0Go1tsGEsmtFryDOJo3dEmqu.jpg",
        "year": 1994,
        "rating": 9.3,
        "overview": "Two imprisoned men bond over a number of years, finding solace and eventual redemption through acts of common decency."
    }
]

# ⭐ Function to convert rating (out of 10) into 1–5 stars
def rating_to_stars(rating):
    stars = round(rating / 2)  # convert 10 scale → 5 scale
    return "⭐" * stars + "☆" * (5 - stars)

# 🎬 Display movies in black box cards
cols = st.columns(3)
for i, movie in enumerate(movies):
    with cols[i % 3]:
        st.markdown(f"""
        <div class="movie-card">
            <img src="{movie['poster']}" width="5000",height="5000">
           <p style="color:white; font-size:30px; margin:5px 0;">
                🎬 <b>{movie['title']}</b>
            </p>
            <p style="color:white; font-size:24px; margin:5px 0;">
                🗓️ Year: {movie['year']}
            </p>
            <p style="color:#FFD700; font-size:22px; margin:5px 0;">
                Rating: {rating_to_stars(movie['rating'])} ({movie['rating']}/10)
            </p>
        </div>
        """,
    unsafe_allow_html=True)
        st.markdown(f"**📖 Overview:** {movie['overview']}")

# Heading
st.markdown("*Where* Every **Story** ***Finds You!🎞️***.")

# Original multi text block
multi = '''👉 _Where every story reaches you on its own.
Movies are not just entertainment; they take us to a completely different world. 🌍🎬
Every movie can make us laugh, cry, force us to think, and make us dream. ❤️
Sometimes, you just need a perfect movie according to your mood.🍿
                            That is why we have built this Movie Recommendation System 
for you.Discover movies according to your choice, interest, and favourite genre. 🔍
Explore stories that you might have never seen before._

_Whether it is a thriller, romance, comedy, or adventure — there is something for every mood. 😍
Now searching for movies has become even easier and smarter.
Now there is no need to scroll repeatedly and wonder, "What should I actually watch?" 😂
                                   Your next favourite movie could be just a click away. 🎥✨
So relax, grab your popcorn 🍿, and start your movie journey.
Inside every movie, a story is hidden, waiting to be discovered. ❤️
And sometimes, a movie becomes a beautiful memory. 🥹
                                                 Keep exploring, keep discovering, and keep 
enjoying movies. 🎬Choose your mood and let the movie take you to a new world. ✨
We hope that our recommendations will make your movie experience even more special.
Search less. Discover more. Watch better. 🔥
                                          Your next cinematic adventure starts right here! 🎥✨
Because a perfect movie is not just watched… it is felt. ❤️🍿
If you want, I can help you refine the phrasing for a specific audience (like making
it more professional or punchier for a social media caption). Let me know how you plan to use this text!_

"_❤️ Romance mood → Romantic movies
😂 Comedy mood → Funny movies
😱 Thriller mood → Thriller movies
🥺 Emotional mood → Emotional movies
🔥 Adventure mood → Adventure movies_"

                                🍿 _*Cinematic & Catchy*_
:-              “Your next favorite movie is just one recommendation away. 🎬✨”
:-              “Don’t just watch a movie — discover an experience. 🍿”
:-               “One search. Endless stories. Your perfect movie awaits.”
:-              “Every mood has a movie. Find yours. 🎭🎬”
:-               “Lights. Camera. Recommendation! 🎥✨”
:-              “Your next adventure begins with a movie.”
:-              “Discover. Watch. Enjoy. Repeat. 🍿”
                        Movies are more than stories on a screen; they are emotions, memories, dreams, and journeys waiting to be discovered. Sometimes, the right movie can change your mood, inspire your thoughts, or simply make your day better. Our Movie Recommendation System helps you find that perfect story, because every mood deserves a movie, and every movie deserves to be discovered.Every movie has a story, every story carries an emotion, and every emotion deserves the perfect moment. Whether you are looking for laughter, romance, adventure, mystery, or inspiration, the right movie is waiting to take you somewhere new. Discover stories that match your mood, explore worlds beyond imagination, and let every recommendation become the beginning of a beautiful cinematic journey.
“Your mood has a story. Let us help you find it. 🎬✨”   
:-                                                                   created by Sanju...❤️'''

# ✅ Wrap with styled div using f-string
styled_multi = f"""
<div style="
    font-family: 'Georgia', serif;   /* font style */
    font-size: 18px;                 /* font size */
    color: #FFFFFF;  
    text-shadow: 0px 0px 8px #FFD700, 0px 0px 15px #FFA500;                  
    line-height: 1.6;
">
{multi}
</div>
"""
# Render styled text
st.markdown(styled_multi, unsafe_allow_html=True)

