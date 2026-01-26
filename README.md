# 🎯 Quizzle - AI-Powered Quiz Platform

A fun, BuzzFeed-style quiz platform that uses AI to generate engaging personality and trivia quizzes.

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
pip install pytrends google-generativeai
```

### 2. Configure API Keys

Edit `config.json` and add your Gemini API key:

```json
{
  "gemini": {
    "api_key": "YOUR_GEMINI_API_KEY_HERE",
    ...
  }
}
```

### 3. Run the Platform

```bash
# Start the web server
npm start

# Visit http://localhost:3001
```

The platform comes with 2 sample quizzes so you can test immediately!

## 🎨 Generating New Quizzes

### Generate a Single Quiz

```bash
# Personality quiz with auto-discovered topic
python pipeline/run_pipeline.py --type personality --category pop_culture

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
| `--batch`, `-b` | Number of quizzes to generate |
| `--skip-images` | Skip image generation |
| `--no-pytrends` | Skip Google Trends, use Gemini only |
| `--list`, `-l` | List all generated quizzes |

## 🔧 Configuration

### Quiz Settings (`config.json`)

```json
{
  "quiz_settings": {
    "personality": {
      "questions_per_quiz": 7,
      "outcomes_count": 4
    },
    "trivia": {
      "questions_per_quiz": 10,
      "options_per_question": 4
    }
  }
}
```

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

2. **Quiz Generation**:
   - Sends structured prompts to Gemini API
   - Generates questions, answers, and outcome descriptions
   - Creates image prompts for visual generation

3. **Image Generation**:
   - Uses Pollinations.ai (free, no API key needed)
   - Generates cover images, question images, and outcome images
   - Images are saved locally and referenced in quiz JSON

4. **Storage**:
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

Built with 💜 by AI assistance • Quizzes by Gemini • Images by Pollinations.ai
