# IELTS Super Learner Agent

https://github.com/user-attachments/assets/8a0012c6-fee7-4bdd-b84d-08618383867f

A CLI + web IELTS learning assistant powered by ZhipuAI **GLM-5.1**. The web app's **Coach** mode runs a real coached loop: it diagnoses your level, then drills your weaknesses by orchestrating practice generation and scoring as GLM tools — all backed by a learner profile that persists in your browser. Live demo: https://ielts-super-learner.streamlit.app/

## Features

- **🧑‍🏫 AI Coach** (web): a GLM-5.1 orchestrator that runs a first-contact diagnostic, builds a learner profile (current/target band, exam date, weaknesses), then drills your weakest area by calling Practice + Score as tools. Your profile persists in your browser (localStorage).
- **🎯 Practice Generation**: authentic questions for all 4 skills — Listening, Reading, Writing Task 1 & 2, Speaking Parts 1–3 — with one-click scoring of your answer.
- **📊 AI Scoring**: band scores + criterion-by-criterion feedback for Writing & Speaking, scored against the question using official IELTS band descriptors.
- **📈 Progress Tracking**: practice history and band trend over time.

## Installation

1. Clone the repository and navigate to the project directory

2. Create a virtual environment:
```bash
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

3. Install dependencies:
```bash
pip install -r requirements.txt
```

4. Set up your API key:
```bash
cp .env.example .env
# Edit .env and add your ZHIPUAI_API_KEY from https://open.bigmodel.cn
```

## Usage

### Web app (Coach / Practice / Score)
```bash
streamlit run streamlit_app.py
```
The **Coach** greets you, runs a quick diagnostic, then drills your weakest skill — calling Practice and Score behind the scenes and remembering your profile across sessions (stored in your browser).

### Interactive Coaching (CLI)
A coach that diagnoses your level, then drills your weaknesses:
```bash
python -m ielts_agent tutor            # add --harsh for drill-instructor mode
```

### Generate Practice Questions
```bash
# Writing Task 1 (graph/diagram description)
python -m ielts_agent practice --skill writing --task 1

# Writing Task 2 (essay)
python -m ielts_agent practice --skill writing --task 2

# Speaking Part 2
python -m ielts_agent practice --skill speaking --task 2

# Reading comprehension
python -m ielts_agent practice --skill reading

# Listening
python -m ielts_agent practice --skill listening
```

### Score Your Answer
```bash
# Score a writing task
python -m ielts_agent score --skill writing --task 2 --answer "Your essay here..."

# Score a speaking response
python -m ielts_agent score --skill speaking --answer "Your spoken response here..."
```

### View Progress
```bash
python -m ielts_agent progress
```

## Project Structure

```
ielts/
├── streamlit_app.py         # Web app: Coach / Practice / Score
├── ielts_agent/
│   ├── main.py              # CLI entry point
│   ├── config.py            # Configuration & env loading
│   ├── profile.py           # LearnerProfile (the coach's memory)
│   ├── llm/
│   │   ├── client.py        # GLM-5.1 client: thinking + tool calling
│   │   └── messages.py      # Lightweight chat message types
│   ├── agents/
│   │   ├── tutor.py         # Coach orchestrator (tool-calling loop)
│   │   ├── practice.py      # Practice question generator
│   │   └── scorer.py        # Answer scoring with IELTS rubrics
│   ├── db/
│   │   ├── schema.py        # SQLite schema (+ profiles table)
│   │   └── models.py        # Data models
│   └── prompts/
│       └── ielts_prompts.py # IELTS-specific system prompts
├── data/
│   └── ielts.db             # SQLite database
├── requirements.txt
├── .env.example
└── README.md
```

## Requirements

- Python 3.12+
- BigModel (智谱AI) API key

## References

- [BigModel API Docs](https://docs.bigmodel.cn/cn/api/introduction)
- [IELTS Official Guide](https://www.ielts.org/)
