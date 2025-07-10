# app.py – Final Version (Auto Resume Parsing + Recommendation)
import streamlit as st
import pandas as pd
import re, io, requests
from PIL import Image
import pytesseract
import fitz  # PyMuPDF
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity
import matplotlib.pyplot as plt

# Page config
st.set_page_config(page_title="College Smart Placement Advisor", page_icon="🎓")
st.title("🎓 College Smart Placement Advisor")
st.write("Upload अपना **Resume (PDF/Image/Google Drive)** या नीचे form भर कर personalised career advice पाओ!")

# Load job role data
roles_df = pd.read_csv("job_roles.csv")  # Role, Required_Skills
MASTER_SKILLS = {s.lower() for skills in roles_df["Required_Skills"] for s in skills.split(",")}

def extract_skills(text):
    words = {w.lower() for w in re.findall(r"[A-Za-z+#\.]+", text)}
    return ", ".join(sorted(words & MASTER_SKILLS))

# Upload or URL input
st.subheader("📄 Resume Input")
col1, col2 = st.columns(2)
with col1:
    pdf_file = st.file_uploader("Upload PDF / Image", type=["pdf", "png", "jpg", "jpeg"])
with col2:
    pdf_url = st.text_input("…or paste Google Drive PDF Link")

resume_text = ""

# Read resume
if pdf_file:
    if pdf_file.type == "application/pdf":
        with fitz.open(stream=pdf_file.read(), filetype="pdf") as doc:
            for page in doc:
                resume_text += page.get_text()
    else:
        img = Image.open(pdf_file)
        resume_text = pytesseract.image_to_string(img)

elif pdf_url:
    if "drive.google.com" in pdf_url:
        match = re.search(r"/d/([a-zA-Z0-9_-]+)", pdf_url)
        if match:
            file_id = match.group(1)
            pdf_url = f"https://drive.google.com/uc?id={file_id}"

    if st.button("Fetch PDF"):
        try:
            pdf_bytes = requests.get(pdf_url).content
            with fitz.open(stream=pdf_bytes, filetype="pdf") as doc:
                for page in doc:
                    resume_text += page.get_text()
            st.success("✅ Resume fetched successfully!")
        except Exception as e:
            st.error(f"❌ Resume fetch failed: {e}")

# Auto extract details
auto_name = ""
auto_cgpa = ""
auto_certs = ""

if resume_text:
    for line in resume_text.splitlines():
        if line.strip():
            auto_name = " ".join(line.strip().split()[:2]).title()
            break

    cgpa_match = re.search(r"(\d\.\d{1,2})\s*/\s*10|CGPA", resume_text, re.I)
    perc_match = re.search(r"(\d{2,3})\s*%", resume_text)
    if cgpa_match:
        auto_cgpa = float(cgpa_match.group(1))
    elif perc_match:
        auto_cgpa = round(float(perc_match.group(1)) / 9.5, 2)

    CERT_KEYS = ["aws", "cisco", "coursera", "isro", "google", "microsoft"]
    found = [k.upper() for k in CERT_KEYS if k in resume_text.lower()]
    auto_certs = ", ".join(found)

# Profile form
st.subheader("📝 Quick Profile Form")
with st.form("user_form"):
    name   = st.text_input("Name", value=auto_name)
    cgpa   = st.number_input("CGPA (0–10)", 0.0, 10.0, step=0.1,
                             value=float(auto_cgpa) if auto_cgpa else 0.0)
    skills = st.text_area("Skills (comma-separated)",
                          value=extract_skills(resume_text) if resume_text else "")
    certs  = st.text_area("Certifications", value=auto_certs)
    projs  = st.text_area("Projects", placeholder="Portfolio, ML model …")
    submit = st.form_submit_button("🔍 Get Recommendation")

# Recommendation logic
if submit:
    if not skills.strip():
        st.error("⚠️ Skills field खाली है. Manual लिख या resume upload कर.")
        st.stop()

    profile_doc = ", ".join([skills, certs, projs]).lower()
    docs = [profile_doc] + roles_df["Required_Skills"].str.lower().tolist()
    vecs = TfidfVectorizer().fit_transform(docs)
    sims = cosine_similarity(vecs[0:1], vecs[1:]).flatten()
    roles_df["Match %"] = (sims * 100).round(2)
    top3 = roles_df.sort_values("Match %", ascending=False).head(3)

    # Recommendations
    st.subheader("📊 Recommended Roles")
    for _, r in top3.iterrows():
        st.markdown(f"**{r['Role']}** — {r['Match %']} % match")

    # Skill suggestions
    best = top3.iloc[0]
    role_skills = [s.strip().lower() for s in best["Required_Skills"].split(",")]
    user_skills = [s.strip().lower() for s in skills.split(",")]
    missing = [s for s in role_skills if s not in user_skills]

    st.subheader("🧠 Skill Suggestions")
    if missing:
        st.markdown("इन skills पर काम कर:")
        st.markdown("\n".join([f"- {s.title()}" for s in missing]))
    else:
        st.success("✅ तू already top role के लिए ready है!")

    # Match chart
    st.subheader("📈 Role-wise Match %")
    fig, ax = plt.subplots()
    ax.bar(roles_df["Role"], roles_df["Match %"])
    ax.set_ylabel("Match %")
    ax.set_ylim(0, 100)
    ax.set_xticklabels(roles_df["Role"], rotation=12)
    st.pyplot(fig)

    st.info("💡 Tip: Missing skills को सीख कर progress track कर!")

