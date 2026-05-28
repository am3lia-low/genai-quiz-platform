# 🎯 Quizzle - AI-Powered Quiz Platform

Fun, BuzzFeed-style quiz platform that uses AI to generate engaging personality and trivia quizzes. A mini project of mine while I was having some fun with Gen AI.  

Deployment plans are being made as you explore around!

## ✨ Features

- **AI-Generated Quizzes**: Uses Google's Gemini API to create unique quiz content
- **Trend Discovery**: Finds trending topics via Google Trends (pytrends) or AI suggestions
- **AI Image Generation**: Creates quiz images using Pollinations.ai (free, no API key needed)
- **Two Quiz Types**:
  - 🎭 **Personality Quizzes**: "Which X Are You?" style with outcome mapping
  - 🧠 **Trivia Quizzes**: Test your knowledge with scored questions
- **User Tracking**: Records user names, answers, and outcomes
- **Aggregate Stats**: Shows "X% of people got this result" statistics
- **Beautiful UI**: Modern, responsive design inspired by BuzzFeed

## 📁 Project Structure

```
quiz-platform/
├── pipeline/                 # Quiz generation scripts (Python)
│   ├── trend_discovery.py    # Google Trends + Gemini fallback
│   ├── quiz_generator.py     # Gemini API quiz generation
│   ├── image_generator.py    # Pollinations.ai image generation
│   ├── database.py           # SQLite database operations
│   └── run_pipeline.py       # Main orchestrator
│
├── server/                   # Backend (Node.js)
│   └── app.js                # Express server
│
├── frontend/                 # Web interface
│   ├── index.html            # Quiz gallery page
│   └── quiz.html             # Quiz-taking page
│
├── data/
│   ├── quizzes/              # Generated quiz JSON files
│   │   ├── personality/
│   │   └── trivia/
│   ├── images/               # Generated images
│   └── responses.db          # SQLite database
│
├── config.json               # API keys and settings
├── package.json              # Node.js dependencies
└── README.md
```

## 🚀 Quick Start

### Prerequisites

- **Node.js** 18+ (for the web server)
- **Python** 3.10+ (for quiz generation)
- **Gemini API Key** (free at https://makersuite.google.com/app/apikey)

### 1. Install Dependencies

```bash
# Node.js dependencies (for web server)
cd quiz-platform
npm install

# Python dependencies (for quiz generation)
pip install -r requirements.txt
```

### 2. Configure API Keys

Copy the example config, then create a local `.env` for Gemini API keys:

```bash
cp example.config.json config.json
cp .env.example .env
```

```env
GEMINI_API_KEY_1=your_first_key
GEMINI_API_KEY_2=your_second_key
GEMINI_API_KEY_3=your_third_key
```

The pipeline tries key 1 first, then automatically rotates to key 2 and key 3 if a Gemini request fails. The older `config.json` `gemini.api_key` field still works as a fallback.

### 3. Run the Platform

```bash
# Start the web server
npm start

# Visit http://localhost:3001
```

If `data/` is empty in a fresh clone, generate quizzes with the pipeline commands below before opening the gallery.

## 🎨 Generating New Quizzes

### Generate a Single Quiz

```bash
# Personality quiz with auto-discovered topic
python pipeline/run_pipeline.py --type personality --category pop_culture

# Show a plan without spending on full quiz or images
python pipeline/run_pipeline.py --type personality --category movies --topic "Harry Potter" --dry-plan

# Choose from discovered topics interactively
python pipeline/run_pipeline.py --type trivia --category history --choose-topic

# Trivia quiz with specific topic
python pipeline/run_pipeline.py --type trivia --category history --topic "Ancient Rome"

# Skip image generation for faster testing
python pipeline/run_pipeline.py --type personality --skip-images
```

### Generate Multiple Quizzes

```bash
# Generate 2 quizzes (1 personality, 1 trivia)
python pipeline/run_pipeline.py --batch 2

# Generate 4 personality quizzes
python pipeline/run_pipeline.py --batch 4 --type personality
```

### List Generated Quizzes

```bash
python pipeline/run_pipeline.py --list
```

### Command Line Options

| Option | Description |
|--------|-------------|
| `--type`, `-t` | Quiz type: `personality` or `trivia` |
| `--category`, `-c` | Category (pop_culture, history, movies, etc.) |
| `--topic` | Specific topic (optional, will discover if not provided) |
| `--choose-topic` | Show discovered topics and choose one interactively |
| `--shape` | `auto` lets Gemini plan counts; `fixed` uses config counts |
| `--quality` | `economy`, `standard`, or `editorial` model usage profile |
| `--dry-plan` | Print the quiz plan and stop before full generation |
| `--batch`, `-b` | Number of quizzes to generate |
| `--skip-images` | Skip image generation |
| `--no-pytrends` | Skip Google Trends, use Gemini only |
| `--list`, `-l` | List all generated quizzes |

## 🔧 Configuration

### Quiz Settings (`config.json`)

```json
{
  "models": {
    "planner": "gemini-2.5-flash",
    "generator": "gemini-2.5-flash",
    "fallback_planner": "gemini-2.5-pro"
  },
  "quiz_settings": {
    "personality": {
      "questions_per_quiz": 7,
      "outcomes_count": 4,
      "options_per_question": 4,
      "min_questions": 5,
      "max_questions": 10,
      "min_outcomes": 3,
      "max_outcomes": 6,
      "min_options_per_question": 3,
      "max_options_per_question": 5
    },
    "trivia": {
      "questions_per_quiz": 10,
      "options_per_question": 4,
      "min_questions": 6,
      "max_questions": 12,
      "min_options_per_question": 3,
      "max_options_per_question": 5
    }
  }
}
```

`--shape auto` uses Gemini to plan the question count, outcome count, options per question, and scoring style within the configured bounds. `--shape fixed` keeps the legacy fixed counts. The generator requests structured JSON from Gemini and validates the result locally before saving.

### Available Categories

**Personality**: pop_culture, mythology, psychology, movies, food, travel

**Trivia**: pop_culture, sports, nature, history, science, geography

## 📊 API Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/quizzes` | GET | List all quizzes |
| `/api/quizzes/:id` | GET | Get quiz details |
| `/api/quizzes/:id/responses` | POST | Submit quiz response |
| `/api/quizzes/:id/stats` | GET | Get quiz statistics |
| `/api/responses/:id` | GET | Get specific response |

## 💡 How It Works

### Quiz Generation Pipeline

1. **Trend Discovery**: 
   - Tries to fetch trending topics from Google Trends via `pytrends`
   - Falls back to Gemini AI suggestions if pytrends fails or is disabled
   - `--choose-topic` lets you pick from discovered topics for one-off generation

2. **Quiz Planning**:
   - Uses fixed config counts or asks Gemini to plan the quiz shape
   - Plans question count, options per question, outcome count, scoring style, and image direction
   - Validates the plan against local min/max bounds

3. **Quiz Generation**:
   - Sends structured-output requests to Gemini API
   - Generates questions, answers, outcomes, explanations, and image prompts
   - Validates question counts, option counts, outcome mappings, and trivia answer indexes

4. **Image Generation**:
   - Uses Unsplash for cover/outcome images when configured
   - Uses Pollinations.ai for question images and image fallbacks
   - Images are saved locally and referenced in quiz JSON

5. **Storage**:
   - Quiz content saved as JSON files
   - User responses stored in SQLite database
   - Statistics calculated from response data

### User Flow

1. User visits gallery → sees available quizzes
2. Clicks a quiz → enters their name
3. Answers questions → personality: picks outcome, trivia: right/wrong
4. Sees results → personality: which character, trivia: score
5. Views stats → "X% of people got this result"

## 🎯 Tips for Best Results

1. **Gemini Prompts**: The quiz generator uses carefully crafted prompts. Edit `quiz_generator.py` to customize the style.

2. **Image Quality**: Pollinations.ai quality varies. For production, consider:
   - Stable Diffusion API
   - DALL-E
   - Pre-made image libraries

3. **Rate Limits**: 
   - pytrends: ~10-20 requests before rate limiting
   - Gemini free tier: 60 requests/minute
   - Pollinations.ai: Add delays between requests (built-in 2s delay)

4. **Scaling**: For production deployment:
   - Use PostgreSQL instead of SQLite
   - Add image CDN
   - Implement caching

## 🐛 Troubleshooting

**pytrends rate limiting**: Use `--no-pytrends` flag to skip Google Trends

**Gemini errors**: Check your API key and quota at https://makersuite.google.com/

**Images not loading**: Check `data/images/` folder and file permissions

**Database errors**: Delete `data/responses.db` to reset

## 📝 License

MIT License - feel free to use and modify!

---

Kindly built with AI assistance • Quizzes by Gemini • Images by Pollinations.ai
