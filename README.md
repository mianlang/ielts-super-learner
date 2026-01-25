# IELTS Super Learner Agent

(Demo Video)[https://github.com/user-attachments/assets/8a0012c6-fee7-4bdd-b84d-08618383867f]

A CLI-based IELTS learning assistant powered by LangChain and BigModel (智谱AI/GLM).

## Features

- **Interactive Tutoring**: Ask questions about IELTS concepts, grammar, vocabulary, and strategies
- **Practice Generation**: Generate practice questions for all 4 IELTS skills
  - Listening
  - Reading
  - Writing Task 1 & 2
  - Speaking Part 1, 2, & 3
- **AI Scoring**: Get band scores and feedback based on official IELTS rubrics
- **Progress Tracking**: Track your practice history and improvement over time

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

### Interactive Tutoring
Ask questions about IELTS concepts:
```bash
python -m ielts_agent tutor
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
├── ielts_agent/
│   ├── main.py              # CLI entry point
│   ├── config.py            # Configuration & env loading
│   ├── llm/
│   │   └── client.py        # BigModel LLM wrapper
│   ├── agents/
│   │   ├── tutor.py         # Q&A tutoring agent
│   │   ├── practice.py      # Practice question generator
│   │   └── scorer.py        # Answer scoring with IELTS rubrics
│   ├── db/
│   │   ├── schema.py        # SQLite schema
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
