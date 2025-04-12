import os
import streamlit as st
import google.generativeai as genai
import pandas as pd
from typing import Dict, Any
import fitz  # PyMuPDF
from docx import Document


genai.configure(api_key="AIzaSyDw9KBTlo6nJ30VKQqjSNd_L02beWnXpL0")

generation_config = {
    "temperature": 1,
    "top_p": 0.95,
    "top_k": 40,
    "max_output_tokens": 8192,
    "response_mime_type": "text/plain",
}

model = genai.GenerativeModel(
    model_name="gemini-1.5-flash-8b",
    generation_config=generation_config,
)
chat_session = model.start_chat(history=[])

admission_criteria = """
Eligibility Criteria for Admission
1. Age Limit:
   - Student must be less than 21 years old at the time of admission.
2. Academic Qualification:
   - Must have passed 10+2 from a Recognized Higher Secondary Education Board.
   - Must have studied Physics, Chemistry, and Mathematics (PCM) as core subjects.
   - Minimum 90% aggregate marks in PCM subjects.
3. Required Documents (Mandatory for all students):
   - Student Resume (PDF format)
   - Student Marksheet (10+2)
4. Additional Documents (Only for students requesting loan):
   - Parent Income Certificate
   - Loan Request Document
5. Loan Eligibility Criteria:
   - Loan will only be approved if Parents' Annual Income is less than ₹2,50,000.
"""

st.title("🎓 University Admission Workflow")
uploaded_files = st.file_uploader("Upload Application Documents", type=["pdf", "docx", "txt"], accept_multiple_files=True)

def extract_text_from_pdf(file):
    doc = fitz.open(stream=file.read(), filetype="pdf")
    return "\n".join(page.get_text("text") for page in doc)

def extract_text_from_docx(file):
    return "\n".join(p.text for p in Document(file).paragraphs)

def extract_text_from_file(file):
    ext = file.name.split(".")[-1].lower()
    file.seek(0)
    if ext == "pdf": return extract_text_from_pdf(file)
    if ext == "docx": return extract_text_from_docx(file)
    if ext == "txt": return file.read().decode("utf-8")
    return "Unsupported format"

def doc_checker_run(state):
    results = []
    for app in state["app_files"]:
        text = "\n".join(extract_text_from_file(f) for f in app["files"])
        prompt = f"""
{admission_criteria}
Given the application content for {app['name']} ({app['email']}):
{text}

Check and list:
1. Present documents
2. Missing documents
3. Applicant email
4. Applicant name
"""
        res = chat_session.send_message(prompt).text
        app["doc_check"] = res
        results.append(app)
    state["doc_checked"] = results
    return state

def shortlister_run(state):
    shortlisted = []
    for app in state["doc_checked"]:
        text = "\n".join(extract_text_from_file(f) for f in app["files"])
        prompt = f"""
{admission_criteria}
Based on the application content:
{text}

Is the applicant eligible for admission? Justify in 2 lines.
Then say:
- Shortlist: Yes/No
"""
        res = chat_session.send_message(prompt).text
        app["shortlist_status"] = res
        if "Shortlist: Yes" in res:
            shortlisted.append(app)
    state["shortlisted"] = shortlisted
    return state

def loan_agent_run(state):
    loans = []
    for app in state["shortlisted"]:
        text = "\n".join(extract_text_from_file(f) for f in app["files"])
        prompt = f"""
{admission_criteria}
Review this content for loan eligibility:
{text}

Extract:
- Parents' Annual Income
- Eligible for Loan: Yes/No
- Recommended Loan Amount
"""
        res = chat_session.send_message(prompt).text
        app["loan"] = res
        loans.append(app)
    state["loan_processed"] = loans
    return state

def admission_officer_run(state):
    summary = []
    for app in state["loan_processed"]:
        summary.append({
            "Name": app["name"],
            "Email": app["email"],
            "Shortlisted": "Yes" if "Shortlist: Yes" in app.get("shortlist_status", "") else "No",
            "Loan Status": app.get("loan", "Not Applied")
        })
    df = pd.DataFrame(summary)
    st.dataframe(df)
    st.download_button("📥 Download Final Admissions Report", df.to_csv(index=False), "final_admissions.csv", "text/csv")
    return state

if uploaded_files:
    st.success("Files uploaded successfully ✅")
    app_files = [{"name": f.name.split(".")[0], "email": "unknown@example.com", "files": [f]} for f in uploaded_files]
    state = {"app_files": app_files}

    st.subheader("🔍 Document Check")
    state = doc_checker_run(state)
    for app in state["doc_checked"]:
        st.markdown(f"**🧾 Applicant: {app['name']}**")
        st.code(app["doc_check"])

    st.subheader("📋 Shortlisting Results")
    state = shortlister_run(state)
    for app in state["doc_checked"]:
        st.markdown(f"**👤 {app['name']}**")
        st.code(app.get("shortlist_status", "Not evaluated"))

    st.subheader("💸 Loan Evaluation")
    state = loan_agent_run(state)
    for app in state["loan_processed"]:
        st.markdown(f"**💼 {app['name']}**")
        st.code(app.get("loan", "Not applied or not eligible"))

    st.subheader("📑 Final Report")
    admission_officer_run(state)

