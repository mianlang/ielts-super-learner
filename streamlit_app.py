"""IELTS Super Learner - Streamlit Web App"""

import os
import streamlit as st

# Load secrets: Streamlit Cloud takes priority, then .env file
if "ZHIPUAI_API_KEY" in st.secrets:
    os.environ["ZHIPUAI_API_KEY"] = st.secrets["ZHIPUAI_API_KEY"]
else:
    from dotenv import load_dotenv
    load_dotenv()

from ielts_agent.agents.tutor import TutorAgent
from ielts_agent.agents.practice import PracticeAgent
from ielts_agent.agents.scorer import ScorerAgent

# Page config
st.set_page_config(
    page_title="IELTS Super Learner",
    page_icon="🎓",
    layout="centered",
)

# Custom CSS
st.markdown("""
<style>
    .main-header {
        text-align: center;
        padding: 2rem 0;
    }
    .chat-message {
        padding: 1rem;
        border-radius: 0.5rem;
        margin-bottom: 1rem;
    }
    .user-message {
        background-color: #f0f0f0;
        text-align: right;
    }
    .assistant-message {
        background-color: #e3f2fd;
    }
</style>
""", unsafe_allow_html=True)

# Check API key
if not os.getenv("ZHIPUAI_API_KEY"):
    st.error("⚠️ ZHIPUAI_API_KEY not configured. Please set it in the environment variables.")
    st.info("To run locally: create a `.env` file with `ZHIPUAI_API_KEY=your_key`")
    st.stop()

# Initialize session state
if "messages" not in st.session_state:
    st.session_state.messages = []
if "tutor" not in st.session_state:
    st.session_state.tutor = TutorAgent(proactive=True, harsh=False)
if "mode" not in st.session_state:
    st.session_state.mode = "friendly"

# Header
st.markdown("""
<div class="main-header">
    <h1>🎓 IELTS Super Learner</h1>
    <p>Your AI-powered IELTS study companion</p>
</div>
""", unsafe_allow_html=True)

# Mode selection
col1, col2, col3 = st.columns(3)
with col1:
    if st.button("📝 Tutor", use_container_width=True):
        st.session_state.mode = "tutor"
        st.session_state.tutor = TutorAgent(proactive=True, harsh=False)
        st.session_state.messages = []
        st.rerun()
with col2:
    if st.button("🎯 Practice", use_container_width=True):
        st.session_state.mode = "practice"
        st.session_state.messages = []
        st.rerun()
with col3:
    if st.button("📊 Score", use_container_width=True):
        st.session_state.mode = "score"
        st.session_state.messages = []
        st.rerun()

st.divider()

# Tutor Mode
if st.session_state.mode == "tutor":
    st.subheader("💬 AI Tutor")

    # Harsh mode toggle
    harsh = st.toggle("🔥 Harsh Mode (Drill Instructor)", value=False)
    if harsh != st.session_state.tutor.harsh:
        st.session_state.tutor.set_harsh(harsh)
        st.session_state.tutor.reset_conversation()
        st.session_state.messages = []
        st.rerun()

    # Start conversation button
    if not st.session_state.messages:
        if st.button("🚀 Start Conversation", type="primary"):
            with st.chat_message("assistant"):
                greeting = st.write_stream(st.session_state.tutor.start_conversation_stream())
            st.session_state.messages.append({"role": "assistant", "content": greeting})
            st.rerun()

    # Chat interface
    for msg in st.session_state.messages:
        with st.chat_message(msg["role"]):
            st.markdown(msg["content"])

    if prompt := st.chat_input("Type your message..."):
        st.session_state.messages.append({"role": "user", "content": prompt})
        with st.chat_message("user"):
            st.markdown(prompt)

        with st.chat_message("assistant"):
            response = st.write_stream(st.session_state.tutor.ask_proactive_stream(prompt))
        st.session_state.messages.append({"role": "assistant", "content": response})

# Practice Mode
elif st.session_state.mode == "practice":
    st.subheader("🎯 Practice Mode")

    skill = st.selectbox("Select Skill", ["writing", "speaking", "reading", "listening"])
    task = st.selectbox("Select Task", ["1", "2"] if skill in ["writing", "speaking"] else ["N/A"])

    if st.button("Generate Question", type="primary"):
        practice_agent = PracticeAgent()
        with st.spinner("Generating question..."):
            question = st.write_stream(practice_agent.generate_practice_stream(
                skill, task=int(task) if task != "N/A" else None
            ))
        st.session_state.messages.append({"role": "question", "content": question})

    if st.session_state.messages:
        for msg in st.session_state.messages:
            st.info(msg["content"])

        answer = st.text_area("Your Answer:", height=200)
        if st.button("Submit Answer"):
            st.success("Answer submitted! Use Score mode to get feedback.")

# Score Mode
elif st.session_state.mode == "score":
    st.subheader("📊 Score Your Answer")

    skill = st.selectbox("Select Skill", ["writing", "speaking", "reading", "listening"])
    answer = st.text_area("Paste your answer here:", height=200)

    if st.button("Get Score", type="primary"):
        if answer:
            with st.spinner("Scoring..."):
                scorer = ScorerAgent()
                result = scorer.score(skill, answer)

                band_score = result.get("overall_band_score", 0)
                st.success(f"**Band Score: {band_score}**")

                st.subheader("Feedback")
                st.info(result.get("feedback", "No feedback available."))
        else:
            st.warning("Please enter your answer first.")

# Footer
st.divider()
st.markdown("""
<div style="text-align: center; color: #666; font-size: 0.9rem;">
    <p>Powered by GLM-4 | Get your free API key at <a href="https://open.bigmodel.cn/usercenter/apikeys" target="_blank">ZhipuAI</a></p>
    <p><a href="https://github.com/mianlang/ielts-super-learner" target="_blank">GitHub</a></p>
</div>
""", unsafe_allow_html=True)
