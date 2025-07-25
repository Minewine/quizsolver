# Joe.ie Quiz Solver

AI-powered quiz solver for Joe.ie Friday Pub Quiz.

## Setup

1. Install dependencies:
```bash
pip install -r requirements.txt
playwright install
```

2. Add your OpenRouter API key to `.env`:
```
OPENROUTER_API_KEY=your-key-here
```

## Usage

**Automated Solver:**
```bash
python quiz_solver.py
```

**Manual Assistant:**
```bash
python quiz_assistant.py
```
Copy question → Press Enter → Get AI answer

## Files

- `quiz_solver.py` - Automated browser-based solver
- `quiz_assistant.py` - Manual copy/paste helper