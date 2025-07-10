# app.py – Fixed CSV parsing & skill‑match logic
import streamlit as st
import pandas as pd
import re, io, requests
from PIL import Image
import pytesseract
import fitz  # PyMuPDF
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity
import matplotlib.pyplot as plt

st.set_page_config(page_title="College Smart Placement Advisor", page_icon="🎓")
st.title("🎓 College Smart Placement Advisor")
st.write("Upload अपना **Resume (PDF / Image / Drive link)** या form भर कर personalised career advice पाओ!")

# ────────────────────────────────
# 1.  Load job_roles.csv (quotes‑safe)
roles_df = pd.read_csv("job_roles.csv")
# master skills set
MASTER_SKILLS = {s.lower() for skills in roles_df["Required_Skills"] for s in skills.split(",")}

def extract_skills(text: str) -> str:
    words = {w.lower() for w in re.findall(r"[A-Za-z+#\.]+", text)}
    return ", ".join(sorted(words & MASTER_SKILLS))

# ────────────────────────────────
# 2.  Resume Input
st.subheader("📄 Resume Input")
c1, c2 = st.columns(2)
with c1:
    pdf_file = st.file_uploader("Upload PDF / Image", type=["pdf", "png", "jpg", "jpeg"])
with c2:
    pdf_url = st.text_input("…or paste Google Drive link")

resume_text = ""

def read_pdf_bytes(pdf_bytes):
    text = ""
    with fitz.open(stream=pdf_bytes, filetype="pdf") as doc:
        for page in doc:
            text += page.get_text()
    return text

if pdf_file:
    if pdf_file.type == "application/pdf":
        resume_text = read_pdf_bytes(pdf_file.read())
    else:
        resume_text = pytesseract.image_to_string(Image.open(pdf_file))
elif pdf_url:
    if "drive.google.com" in pdf_url:
        m = re.search(r"/d/([A-Za-z0-9_-]+)", pdf_url)
        if m:
            pdf_url = f"https://drive.google.com/uc?id={m.group(1)}"
    if st.button("Fetch PDF"):
        try:
            resume_text = read_pdf_bytes(requests.get(pdf_url).content)
            st.success("✅ Resume fetched!")
        except Exception as e:
            st.error(f"❌ {e}")

# ────────────────────────────────
# 3.  Auto‑extract Name / CGPA / Certs
auto_name = auto_cgpa = auto_certs = ""
if resume_text:
    for line in resume_text.splitlines():
        if line.strip():
            auto_name = " ".join(line.strip().split()[:2]).title()
            break
    cg = re.search(r"(\d\.\d{1,2})\s*/\s*10|CGPA", resume_text, re.I)
    pc = re.search(r"(\d{2,3})\s*%", resume_text)
    if cg:
        auto_cgpa = float(cg.group(1))
    elif pc:
        auto_cgpa = round(float(pc.group(1)) / 9.5, 2)
    CERT_KEYS = ["aws", "cisco", "coursera", "isro", "google"]
    auto_certs = ", ".join([k.upper() for k in CERT_KEYS if k in resume_text.lower()])

# ────────────────────────────────
# 4.  Form
st.subheader("📝 Quick Profile Form")
with st.form("user_form"):
    name   = st.text_input("Name", value=auto_name)
    cgpa   = st.number_input("CGPA (0–10)", min_value=0.0, max_value=10.0, step=0.1, value=float(auto_cgpa) if auto_cgpa else 0.0)
    skills = st.text_area("Skills (comma‑sep)", value=extract_skills(resume_text) if resume_text else "")
    certs  = st.text_area("Certifications", value=auto_certs)
    projs  = st.text_area("Projects")
    submit = st.form_submit_button("🔍 Get Recommendation")


# ────────────────────────────────
# 5.  Recommendation
if submit:
    if not skills.strip():
        st.error("⚠️  Skills blank hain, manually add karo.")
        st.stop()

    profile_doc = ", ".join([skills, certs, projs]).lower()
    docs  = [profile_doc] + roles_df["Required_Skills"].str.lower().tolist()
    vecs  = TfidfVectorizer().fit_transform(docs)
    sims  = cosine_similarity(vecs[0:1], vecs[1:]).flatten()
    roles_df["Match %"] = (sims * 100).round(2)
    top3 = roles_df.sort_values("Match %", ascending=False).head(3)

    st.subheader("📊 Recommended Roles")
    for _, r in top3.iterrows():
        st.markdown(f"**{r['Role']}** — {r['Match %']} % match")

    # skill suggestions for best role
    best = top3.iloc[0]
    role_skills = [s.strip().lower() for s in best["Required_Skills"].split(",")]
    user_skills = [s.strip().lower() for s in skills.split(",")]
    missing = [sk for sk in role_skills if sk not in user_skills]

    st.subheader("🧠 Skill Suggestions")
    if missing:
        st.markdown("इन skills पर काम करो:")
        st.markdown("\n".join(f"- {m.title()}" for m in missing))
    else:
        st.success("✅ तू already ready है!")

    # bar chart
    st.subheader("📈 Role-wise Match %")
    fig, ax = plt.subplots()
    ax.bar(roles_df["Role"], roles_df["Match %"])
    ax.set_ylim(0, 100)
    ax.set_ylabel("Match %")
    ax.set_xticklabels(roles_df["Role"], rotation=12)
    st.pyplot(fig)

    st.info("💡 Missing skills को सीख कर progress track कर!")

