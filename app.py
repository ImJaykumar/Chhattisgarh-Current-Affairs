import os
import json
import re
from datetime import datetime, timedelta, timezone

import streamlit as st
import feedparser
from bs4 import BeautifulSoup
from google import genai
from google.genai import types
from tenacity import retry, stop_after_attempt, wait_exponential


# =========================================================
# PAGE CONFIG
# =========================================================

st.set_page_config(
    page_title="CG Daily Current Affairs",
    page_icon="🟢",
    layout="wide"
)

st.title("🟢 CG Daily Current Affairs Generator")
st.caption(
    "CGPSC • CG Vyapam • CGSSB • Teacher • Assistant Grade • DEO"
)


# =========================================================
# SIDEBAR
# =========================================================

st.sidebar.header("⚙️ Settings")

api_key = st.sidebar.text_input(
    "Gemini API Key",
    value=os.environ.get("GEMINI_API_KEY", ""),
    type="password"
)

model_name = st.sidebar.text_input(
    "Gemini Model",
    value="gemini-3.6-flash"
)

max_per_feed = st.sidebar.slider(
    "प्रति Feed कितनी खबरें?",
    3,
    20,
    8
)

recent_hours = st.sidebar.slider(
    "कितने घंटे की खबरें?",
    12,
    96,
    48
)

question_count = st.sidebar.slider(
    "MCQ की संख्या",
    5,
    20,
    10
)


# =========================================================
# RSS SOURCES
# =========================================================

CG_RSS_SOURCES = [

    # -----------------------------------------------------
    # Main CG
    # -----------------------------------------------------

    (
        "Patrika CG",
        "https://cms.patrika.com/googlefeed/blog/location/chhattisgarh-news"
    ),

    (
        "Live Hindustan CG",
        "https://api.livehindustan.com/feeds/rss/chhattisgarh/rssfeed.xml"
    ),

    (
        "Google News CG",
        "https://news.google.com/rss/search?q=Chhattisgarh&hl=hi&gl=IN&ceid=IN:hi"
    ),

    # -----------------------------------------------------
    # District Feeds
    # -----------------------------------------------------

    (
        "Raipur",
        "https://api.livehindustan.com/feeds/rss/chhattisgarh/raipur/rssfeed.xml"
    ),

    (
        "Bilaspur",
        "https://api.livehindustan.com/feeds/rss/chhattisgarh/bilaspur/rssfeed.xml"
    ),

    (
        "Korba",
        "https://api.livehindustan.com/feeds/rss/chhattisgarh/korba/rssfeed.xml"
    ),

    (
        "Bastar",
        "https://api.livehindustan.com/feeds/rss/chhattisgarh/bastar/rssfeed.xml"
    ),

    (
        "Bijapur",
        "https://api.livehindustan.com/feeds/rss/chhattisgarh/bijapur/rssfeed.xml"
    ),

    (
        "Janjgir Champa",
        "https://api.livehindustan.com/feeds/rss/chhattisgarh/janjgir-champa/rssfeed.xml"
    ),

    (
        "Jashpur",
        "https://api.livehindustan.com/feeds/rss/chhattisgarh/jashpur/rssfeed.xml"
    ),

    (
        "Mahasamund",
        "https://api.livehindustan.com/feeds/rss/chhattisgarh/mahasamund/rssfeed.xml"
    ),

    (
        "Mungeli",
        "https://api.livehindustan.com/feeds/rss/chhattisgarh/mungeli/rssfeed.xml"
    ),

    (
        "Rajnandgaon",
        "https://api.livehindustan.com/feeds/rss/chhattisgarh/rajnandgaon/rssfeed.xml"
    ),

    (
        "Raigarh",
        "https://api.livehindustan.com/feeds/rss/chhattisgarh/bilaspur/rssfeed.xml"
    ),

    (
        "Sarguja",
        "https://api.livehindustan.com/feeds/rss/chhattisgarh/sarguja/rssfeed.xml"
    ),

    (
        "Sukma",
        "https://api.livehindustan.com/feeds/rss/chhattisgarh/sukma/rssfeed.xml"
    ),
]


# =========================================================
# OFFICIAL GOVERNMENT SOURCES
# =========================================================

OFFICIAL_SOURCES = {

    "CG Public Relations":
        "https://jansampark.cg.gov.in/",

    "CG Samvad":
        "https://samvad.cg.nic.in/",

    "CG Government":
        "https://cgstate.gov.in/",

    "Finance Department":
        "https://finance.cg.gov.in/",

    "CG Vidhan Sabha":
        "https://cgvidhansabha.gov.in/",

    "CG Health Department":
        "https://health.cg.gov.in/",

    "CG Agriculture":
        "https://agriportal.cg.nic.in/",

    "CG Tribal Department":
        "https://tribal.cg.gov.in/",
}


# =========================================================
# KEYWORDS
# =========================================================

IMPORTANT_KEYWORDS = [

    "योजना",
    "मिशन",
    "नीति",
    "अभियान",
    "परियोजना",
    "उद्घाटन",
    "शिलान्यास",
    "कैबिनेट",
    "मंत्रिमंडल",
    "मुख्यमंत्री",
    "राज्यपाल",

    "नियुक्त",
    "नियुक्ति",
    "अध्यक्ष",
    "पुरस्कार",
    "सम्मान",
    "अवार्ड",
    "पदक",

    "निवेश",
    "उद्योग",
    "करोड़",
    "बजट",
    "रिपोर्ट",
    "सूचकांक",
    "इंडेक्स",

    "खिताब",
    "विजेता",
    "प्रतियोगिता",
    "चैंपियन",
    "टूर्नामेंट",

    "पर्यावरण",
    "वन",
    "वन्यजीव",
    "रामसर",
    "राष्ट्रीय उद्यान",
    "अभयारण्य",

    "जनजाति",
    "आदिवासी",
    "संस्कृति",
    "लोकनृत्य",
    "विरासत",

    "शिक्षा",
    "विश्वविद्यालय",
    "स्कूल",

    "स्वास्थ्य",
    "अस्पताल",

    "कृषि",
    "किसान",

    "AI",
    "कृत्रिम बुद्धिमत्ता",
    "विज्ञान",
    "तकनीक",
    "ISRO",
]


IGNORE_KEYWORDS = [

    "हत्या",
    "चोरी",
    "लूट",
    "मारपीट",
    "अपराध",
    "दुर्घटना",
    "आत्महत्या",
    "फिल्म",
    "मनोरंजन",
    "सेलिब्रिटी",
    "ज्योतिष",
    "राशिफल",
]


CG_KEYWORDS = [

    "छत्तीसगढ़",
    "chhattisgarh",
    "रायपुर",
    "बिलासपुर",
    "कोरबा",
    "दुर्ग",
    "बस्तर",
    "सरगुजा",
    "कांकेर",
    "मुंगेली",
    "महासमुंद",
    "राजनांदगांव",
    "रायगढ़",
    "जशपुर",
    "बीजापुर",
    "सुकमा",
    "जांजगीर",
    "बलौदाबाजार",
    "बलरामपुर",
    "कबीरधाम",
    "गरियाबंद",
    "धमतरी",
    "कांकेर",
    "नारायणपुर",
    "कोंडागांव",
]


# =========================================================
# SESSION STATE
# =========================================================

if "raw_articles" not in st.session_state:
    st.session_state.raw_articles = []

if "selected_articles" not in st.session_state:
    st.session_state.selected_articles = []

if "quiz_data" not in st.session_state:
    st.session_state.quiz_data = None


# =========================================================
# HELPER
# =========================================================

def clean_text(text):

    if not text:
        return ""

    text = BeautifulSoup(
        text,
        "html.parser"
    ).get_text(" ", strip=True)

    text = re.sub(
        r"\s+",
        " ",
        text
    )

    return text.strip()


def normalize(text):

    return re.sub(
        r"\s+",
        " ",
        text.lower()
    ).strip()


def get_date(entry):

    try:

        if entry.get("published_parsed"):

            return datetime(
                *entry.published_parsed[:6],
                tzinfo=timezone.utc
            )

        if entry.get("updated_parsed"):

            return datetime(
                *entry.updated_parsed[:6],
                tzinfo=timezone.utc
            )

    except Exception:

        pass

    return None


# =========================================================
# EXAM SCORE
# =========================================================

def exam_score(title, content):

    text = normalize(
        title + " " + content
    )

    score = 0

    # CG relevance
    for keyword in CG_KEYWORDS:

        if keyword.lower() in text:
            score += 5

    # Exam keywords
    for keyword in IMPORTANT_KEYWORDS:

        if keyword.lower() in text:
            score += 2

    # Negative keywords
    for keyword in IGNORE_KEYWORDS:

        if keyword.lower() in text:
            score -= 5

    return score


# =========================================================
# FETCH NEWS
# =========================================================

def fetch_news():

    articles = []

    headers = {
        "User-Agent":
            "Mozilla/5.0 "
            "(Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 "
            "Chrome/120.0 Safari/537.36"
    }

    source_status = []

    now = datetime.now(timezone.utc)

    cutoff = now - timedelta(
        hours=recent_hours
    )

    for source_name, feed_url in CG_RSS_SOURCES:

        try:

            feed = feedparser.parse(
                feed_url,
                request_headers=headers
            )

            source_count = 0

            for entry in feed.entries[:max_per_feed]:

                title = clean_text(
                    entry.get("title", "")
                )

                summary = clean_text(
                    entry.get(
                        "summary",
                        entry.get(
                            "description",
                            ""
                        )
                    )
                )

                link = entry.get(
                    "link",
                    ""
                )

                if not title:
                    continue

                published = get_date(
                    entry
                )

                # अगर date available है
                # तभी recent filter लगाएं
                if published:

                    if published < cutoff:
                        continue

                content = (
                    summary
                    if summary
                    else title
                )

                score = exam_score(
                    title,
                    content
                )

                articles.append({

                    "id": len(articles),

                    "source": source_name,

                    "title": title,

                    "content": content,

                    "link": link,

                    "published": (
                        published.isoformat()
                        if published
                        else ""
                    ),

                    "score": score,

                })

                source_count += 1

            source_status.append(
                f"✅ {source_name}: {source_count}"
            )

        except Exception as e:

            source_status.append(
                f"❌ {source_name}: "
                f"{str(e)[:100]}"
            )

    return articles, source_status


# =========================================================
# DUPLICATE REMOVAL
# =========================================================

def remove_duplicates(articles):

    unique = {}

    for article in articles:

        key = normalize(
            article["title"]
        )[:180]

        if key not in unique:

            unique[key] = article

        else:

            if (
                article["score"]
                >
                unique[key]["score"]
            ):

                unique[key] = article

    return list(
        unique.values()
    )


# =========================================================
# ANALYZE
# =========================================================

def analyze_articles(articles):

    articles = remove_duplicates(
        articles
    )

    articles.sort(
        key=lambda x: x["score"],
        reverse=True
    )

    return articles


# =========================================================
# GENERATE MCQ
# =========================================================

def generate_quiz(
    selected_articles
):

    if not selected_articles:

        st.error(
            "पहले कम से कम एक news select करें।"
        )

        return None

    news_text = ""

    for i, article in enumerate(
        selected_articles,
        1
    ):

        news_text += f"""

==============================
NEWS {i}
==============================

Source:
{article['source']}

Headline:
{article['title']}

Content:
{article['content']}

Original Link:
{article['link']}

"""


    prompt = f"""
आप CGPSC, CG Vyapam, CGSSB,
Assistant Grade, DEO, Teacher तथा
अन्य छत्तीसगढ़ प्रतियोगी परीक्षाओं के
Current Affairs Expert हैं।

नीचे केवल चुनी गई Chhattisgarh news दी गई हैं।

इनके आधार पर {question_count} high-quality
MCQ तैयार करें।

IMPORTANT:

1. केवल दिए गए source facts का उपयोग करें।

2. कोई fact invent न करें।

3. यदि किसी fact से question बनाना संभव नहीं है,
   उसे छोड़ दें।

4. प्रश्नों में repetition न हो।

5. 4 options दें।

6. Correct answer A/B/C/D में दें।

7. प्रश्न Hindi में हों।

8. Explanation Hindi में हो।

9. Explanation में:
   - सही उत्तर
   - news का relevant fact
   - exam point
   शामिल करें।

10. Source और original link प्रत्येक question के साथ दें।

11. Difficulty:
   - 30% Easy
   - 50% Moderate
   - 20% Hard

12. Priority:
   - Government schemes
   - Cabinet decisions
   - Economy
   - Budget
   - Appointments
   - Awards
   - Sports
   - Environment
   - Tribal affairs
   - Education
   - Health
   - Agriculture
   - Science & Technology
   - Infrastructure
   - Important statistics

13. सामान्य crime/accident/entertainment
   को प्रश्न न बनाएं।

NEWS:
{news_text}
"""


    schema = {

        "type": "OBJECT",

        "properties": {

            "quiz_date": {
                "type": "STRING"
            },

            "state": {
                "type": "STRING"
            },

            "total_questions": {
                "type": "INTEGER"
            },

            "questions": {

                "type": "ARRAY",

                "items": {

                    "type": "OBJECT",

                    "properties": {

                        "question": {
                            "type": "STRING"
                        },

                        "options": {

                            "type": "ARRAY",

                            "items": {
                                "type": "STRING"
                            }
                        },

                        "correct_answer": {
                            "type": "STRING"
                        },

                        "explanation": {
                            "type": "STRING"
                        },

                        "source_name": {
                            "type": "STRING"
                        },

                        "source_link": {
                            "type": "STRING"
                        },

                        "difficulty": {
                            "type": "STRING"
                        },

                        "topic": {
                            "type": "STRING"
                        }

                    },

                    "required": [

                        "question",
                        "options",
                        "correct_answer",
                        "explanation",
                        "source_name",
                        "source_link",
                        "difficulty",
                        "topic"

                    ]
                }
            }
        },

        "required": [

            "quiz_date",
            "state",
            "total_questions",
            "questions"

        ]
    }


    @retry(
        stop=stop_after_attempt(4),
        wait=wait_exponential(
            multiplier=2,
            min=2,
            max=20
        ),
        reraise=True
    )

    def call_gemini():

        client = genai.Client(
            api_key=api_key
        )

        response = client.models.generate_content(

            model=model_name,

            contents=prompt,

            config=types.GenerateContentConfig(

                response_mime_type="application/json",

                response_schema=schema,

                temperature=0.2
            )
        )

        return response


    try:

        response = call_gemini()

        return json.loads(
            response.text
        )

    except Exception as e:

        st.error(
            f"Gemini Error: {e}"
        )

        return None


# =========================================================
# WHATSAPP NORMAL FORMAT
# =========================================================

def whatsapp_normal(quiz):

    text = []

    text.append(
        "📚 *CG DAILY CURRENT AFFAIRS*"
    )

    text.append(
        f"📅 {quiz.get('quiz_date', '')}"
    )

    text.append("")

    for i, q in enumerate(
        quiz["questions"],
        1
    ):

        text.append(
            f"*Q{i}. {q['question']}*"
        )

        for j, option in enumerate(
            q["options"]
        ):

            letter = chr(
                65 + j
            )

            text.append(
                f"{letter}) {option}"
            )

        text.append("")

    text.append(
        "📌 सही उत्तर एवं explanation अगले पोस्ट में।"
    )

    text.append("")

    text.append(
        "📲 Daily CG Current Affairs के लिए Follow करें:"
    )

    text.append(
        "https://whatsapp.com/channel/0029Vab5ugp8F2p5hKCbpY2N"
    )

    return "\n".join(text)


# =========================================================
# WHATSAPP REACTION FORMAT
# =========================================================

def whatsapp_reaction(quiz):

    reactions = [
        "👍",
        "❤️",
        "😮",
        "😢"
    ]

    text = []

    text.append(
        "🔥 *CG DAILY CURRENT AFFAIRS QUIZ*"
    )

    text.append(
        f"📅 {quiz.get('quiz_date', '')}"
    )

    text.append("")

    for i, q in enumerate(
        quiz["questions"],
        1
    ):

        text.append(
            f"*Q{i}. {q['question']}*"
        )

        for j, option in enumerate(
            q["options"]
        ):

            if j < 4:

                text.append(
                    f"{reactions[j]} {option}"
                )

        text.append("")

    text.append(
        "👇 सही विकल्प पर Reaction करें।"
    )

    text.append(
        "📌 सही उत्तर अगले पोस्ट में बताए जाएंगे।"
    )

    text.append("")

    text.append(
        "📲 Channel Follow करें:"
    )

    text.append(
        "https://whatsapp.com/channel/0029Vab5ugp8F2p5hKCbpY2N"
    )

    return "\n".join(text)


# =========================================================
# STEP 1
# FETCH
# =========================================================

st.markdown("## 1️⃣ News Collection")

if st.button(
    "📡 Fetch Latest CG News",
    use_container_width=True
):

    with st.spinner(
        "Latest Chhattisgarh news collect हो रही है..."
    ):

        articles, status = fetch_news()

        st.session_state.raw_articles = articles

    st.success(
        f"✅ {len(articles)} news मिली।"
    )

    with st.expander(
        "📡 Feed Status"
    ):

        for item in status:

            st.write(item)


# =========================================================
# STEP 2
# ANALYZE
# =========================================================

if st.session_state.raw_articles:

    st.markdown("---")

    st.markdown(
        "## 2️⃣ News Analysis"
    )

    if st.button(
        "🔍 Analyze & Filter Important News",
        use_container_width=True
    ):

        analyzed = analyze_articles(
            st.session_state.raw_articles
        )

        st.session_state.raw_articles = analyzed

        st.success(
            f"⭐ {len(analyzed)} unique news तैयार हैं।"
        )


# =========================================================
# STEP 3
# SELECT NEWS
# =========================================================

if st.session_state.raw_articles:

    st.markdown("---")

    st.markdown(
        "## 3️⃣ Important News Select करें"
    )

    st.info(
        "जिस news से Current Affairs question बनाना चाहते हैं "
        "उसे select करें।"
    )

    selected_ids = []

    for article in st.session_state.raw_articles:

        label = (
            f"⭐ {article['score']} | "
            f"{article['source']} | "
            f"{article['title']}"
        )

        checked = st.checkbox(
            label,
            key=f"article_{article['id']}"
        )

        if checked:

            selected_ids.append(
                article["id"]
            )


    selected = [

        article

        for article
        in st.session_state.raw_articles

        if article["id"] in selected_ids

    ]

    st.session_state.selected_articles = selected

    st.write(
        f"✅ Selected: **{len(selected)}** news"
    )


# =========================================================
# STEP 4
# GENERATE MCQ
# =========================================================

if st.session_state.selected_articles:

    st.markdown("---")

    st.markdown(
        "## 4️⃣ Generate MCQ"
    )

    if st.button(
        "🤖 Generate CG Current Affairs MCQ",
        type="primary",
        use_container_width=True
    ):

        with st.spinner(
            "Gemini MCQs तैयार कर रहा है..."
        ):

            quiz = generate_quiz(
                st.session_state.selected_articles
            )

            if quiz:

                st.session_state.quiz_data = quiz

                st.success(
                    "🎉 MCQ Successfully Generated!"
                )


# =========================================================
# STEP 5
# DISPLAY QUIZ
# =========================================================

if st.session_state.quiz_data:

    quiz = st.session_state.quiz_data

    st.markdown("---")

    st.markdown(
        "## 5️⃣ Generated Quiz"
    )

    st.subheader(
        f"📅 {quiz.get('quiz_date', '')}"
    )

    st.write(
        f"Total Questions: "
        f"**{len(quiz.get('questions', []))}**"
    )

    for i, q in enumerate(
        quiz["questions"],
        1
    ):

        st.markdown(
            f"### Q{i}. {q['question']}"
        )

        cols = st.columns(4)

        for j, option in enumerate(
            q["options"]
        ):

            with cols[j]:

                st.info(
                    f"{chr(65+j)}) {option}"
                )

        with st.expander(
            "✅ Answer + Explanation"
        ):

            st.success(
                f"Correct Answer: "
                f"{q['correct_answer']}"
            )

            st.write(
                q["explanation"]
            )

            st.caption(
                f"📌 Topic: {q['topic']}"
            )

            st.caption(
                f"📊 Difficulty: {q['difficulty']}"
            )

            st.caption(
                f"📰 Source: {q['source_name']}"
            )

            if q["source_link"]:

                st.markdown(
                    f"[🔗 Original Source]"
                    f"({q['source_link']})"
                )

        st.markdown("---")


# =========================================================
# STEP 6
# WHATSAPP
# =========================================================

if st.session_state.quiz_data:

    quiz = st.session_state.quiz_data

    st.markdown(
        "## 6️⃣ WhatsApp Content"
    )

    tab1, tab2 = st.tabs(
        [
            "📚 Answer वाला",
            "🔥 Reaction Quiz"
        ]
    )


    with tab1:

        normal = whatsapp_normal(
            quiz
        )

        st.text_area(
            "WhatsApp Answer Format",
            normal,
            height=500
        )


    with tab2:

        reaction = whatsapp_reaction(
            quiz
        )

        st.text_area(
            "WhatsApp Reaction Format",
            reaction,
            height=500
        )


# =========================================================
# EXPORT
# =========================================================

if st.session_state.quiz_data:

    st.markdown("---")

    st.markdown(
        "## 📥 Export"
    )

    json_data = json.dumps(
        st.session_state.quiz_data,
        ensure_ascii=False,
        indent=4
    )

    st.download_button(

        "📥 Download Quiz JSON",

        json_data,

        file_name=(
            f"cg_current_affairs_"
            f"{datetime.now().strftime('%Y_%m_%d')}.json"
        ),

        mime="application/json"
    )


# =========================================================
# OFFICIAL SOURCES
# =========================================================

with st.expander(
    "🏛️ Official Chhattisgarh Sources"
):

    for name, url in OFFICIAL_SOURCES.items():

        st.markdown(
            f"**{name}:** {url}"
        )