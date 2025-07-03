import streamlit as st
import google.generativeai as genai
import os
import sqlite3
import re
from dotenv import load_dotenv

load_dotenv()

API_KEY = os.getenv("API_KEY")
genai.configure(api_key=API_KEY)

# --- SQLite setup ---
conn = sqlite3.connect("translations.db", check_same_thread=False)
cursor = conn.cursor()

cursor.execute("""
CREATE TABLE IF NOT EXISTS translations (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    language_pair TEXT,
    direction TEXT,
    input_text TEXT,
    output_text TEXT,
    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
)
""")
conn.commit()

def save_translation(language_pair, direction, input_text, output_text):
    cursor.execute("""
    INSERT INTO translations (language_pair, direction, input_text, output_text)
    VALUES (?, ?, ?, ?)
    """, (language_pair, direction, input_text, output_text))
    conn.commit()

def get_last_translations(language_pair, limit=5):
    cursor.execute("""
    SELECT id, direction, input_text, output_text
    FROM translations
    WHERE language_pair = ?
    ORDER BY timestamp DESC
    LIMIT ?
    """, (language_pair, limit))
    return cursor.fetchall()

def delete_translation(translation_id):
    cursor.execute("DELETE FROM translations WHERE id = ?", (translation_id,))
    conn.commit()

def extract_words_and_pronunciation(text):
    pattern = r"(<b>\s*Words\s*</b>:\s*.*?)(<br>)(<b>\s*Pronunciation\s*</b>:\s*.*?)(<br>|$)"
    match = re.search(pattern, text, re.DOTALL | re.IGNORECASE)
    if match:
        return match.group(1) + "<br>" + match.group(3)
    else:
        return text

# --- Prompt generators ---
def generate_hokkien_prompt(text):
    return f"""
    Please translate the following English text to Hokkien.

    {text}

    Leave out random explanations, just give the best option.

    Only include the words, the pronunciation guide and usage.

    Format it like this:

    <b> Words </b>: ...
    <br>
    <b> Pronunciation </b>: ...
    <br>
    <b> Usage </b>: ...
    """

def generate_english_prompt(text):
    return f"""
    Please translate the following Hokkien text to English.

    {text}

    Leave out random explanations, just give the best few options and pronunciation.

    Return the replies you are most confident in.
    """

def generate_teochew_prompt(text):
    return f"""
    Please translate the following English text to Teochew.

    {text}

    Leave out random explanations, just give the best option.

    Only include the words, the pronunciation guide and usage.

    Format it like this:

    <b> Words </b>: ...
    <br>
    <b> Pronunciation </b>: ...
    <br>
    <b> Usage </b>: ...
    """

def generate_english_from_teochew_prompt(text):
    return f"""
    Please translate the following Teochew text to English.

    {text}

    Leave out random explanations, just give the best few options and pronunciation.

    Return the replies you are most confident in.
    """

def translate(prompt):
    model = genai.GenerativeModel("gemini-2.5-flash")
    response = model.generate_content(prompt)
    return response.text

# --- Streamlit UI ---
st.title("GEN2061 Translator")

show_history = st.checkbox("Show Recent Translations", value=True)

col1, col2 = st.columns(2)

with col1:
    language_pair = st.selectbox(
        "Select Language Pair",
        ["English ⇄ Hokkien", "English ⇄ Teochew"]
    )

with col2:
    if language_pair == "English ⇄ Hokkien":
        direction = st.radio("Translation Direction", ["English → Hokkien", "Hokkien → English"])
    else:
        direction = st.radio("Translation Direction", ["English → Teochew", "Teochew → English"])

user_input = st.text_area("Enter text to translate", height=150)

if st.button("Translate"):
    if not user_input.strip():
        st.warning("Please enter some text!")
    else:
        with st.spinner("Translating..."):
            try:
                if language_pair == "English ⇄ Hokkien":
                    if direction == "English → Hokkien":
                        prompt = generate_hokkien_prompt(user_input.strip())
                    else:
                        prompt = generate_english_prompt(user_input.strip())
                else:
                    if direction == "English → Teochew":
                        prompt = generate_teochew_prompt(user_input.strip())
                    else:
                        prompt = generate_english_from_teochew_prompt(user_input.strip())

                translation = translate(prompt)

                save_translation(language_pair, direction, user_input.strip(), translation)
                st.success("Translation:")
                st.markdown(translation, unsafe_allow_html=True)

            except Exception as e:
                st.error(f"Error: {e}")

if show_history:
    st.markdown("### Recent translations")
    history = get_last_translations(language_pair, limit=5)
    if history:
        for translation_id, dir_, inp, outp in history:
            with st.container():
                cols = st.columns([9, 1])  
                with cols[0]:
                    st.markdown(f"**Direction:** {dir_}")
                    st.markdown(f"**Input:** {inp}")
                    cleaned_output = extract_words_and_pronunciation(outp)
                    st.markdown("**Output:**")
                    st.markdown(cleaned_output, unsafe_allow_html=True)
                with cols[1]:
                    if st.button("Del", key=f"del_{translation_id}"):
                        delete_translation(translation_id)
                        st.rerun()
            st.write("---")
    else:
        st.write("No recent translations.")
