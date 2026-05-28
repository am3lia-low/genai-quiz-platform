const express = require('express');
const cors = require('cors');
const path = require('path');
const fs = require('fs');
const crypto = require('crypto');
const initSqlJs = require('sql.js');

const app = express();
const PORT = process.env.PORT || 3001;

// Middleware
app.use(cors());
app.use(express.json());
app.use(express.static(path.join(__dirname, '../frontend')));
app.use('/images', express.static(path.join(__dirname, '../data/images')));

// Database setup
let db = null;
const dbPath = path.join(__dirname, '../data/responses.db');

// Ensure data directory exists
const dataDir = path.join(__dirname, '../data');
if (!fs.existsSync(dataDir)) {
  fs.mkdirSync(dataDir, { recursive: true });
}

// Initialize database
async function initDatabase() {
  const SQL = await initSqlJs();
  
  // Load existing database or create new one
  if (fs.existsSync(dbPath)) {
    const fileBuffer = fs.readFileSync(dbPath);
    db = new SQL.Database(fileBuffer);
  } else {
    db = new SQL.Database();
  }
  
  // Create tables
  db.run(`
    CREATE TABLE IF NOT EXISTS responses (
      id TEXT PRIMARY KEY,
      quiz_id TEXT NOT NULL,
      user_name TEXT NOT NULL,
      answers TEXT NOT NULL,
      outcome TEXT,
      score INTEGER,
      created_at TEXT DEFAULT CURRENT_TIMESTAMP
    )
  `);
  
  db.run(`CREATE INDEX IF NOT EXISTS idx_quiz_id ON responses(quiz_id)`);
  
  db.run(`
    CREATE TABLE IF NOT EXISTS quizzes (
      id TEXT PRIMARY KEY,
      type TEXT NOT NULL,
      category TEXT NOT NULL,
      title TEXT NOT NULL,
      created_at TEXT DEFAULT CURRENT_TIMESTAMP,
      play_count INTEGER DEFAULT 0
    )
  `);
  
  saveDatabase();
  console.log('Database initialized');
}

// Save database to file
function saveDatabase() {
  const data = db.export();
  const buffer = Buffer.from(data);
  fs.writeFileSync(dbPath, buffer);
}

// Helper: Generate short ID
function generateId() {
  return crypto.randomUUID();
}

// Helper: Run a parameterized SELECT query and return objects.
function selectRows(sql, params = []) {
  const stmt = db.prepare(sql);
  stmt.bind(params);

  const rows = [];
  while (stmt.step()) {
    rows.push(stmt.getAsObject());
  }
  stmt.free();

  return rows;
}

function calculatePersonalityOutcome(answers) {
  const counts = {};
  answers.forEach(outcome => {
    counts[outcome] = (counts[outcome] || 0) + 1;
  });

  let topOutcome = null;
  let topCount = 0;
  Object.entries(counts).forEach(([outcome, count]) => {
    if (count > topCount) {
      topOutcome = outcome;
      topCount = count;
    }
  });

  return topOutcome;
}

function validateResponsePayload(quiz, payload) {
  const userName = typeof payload.userName === 'string' ? payload.userName.trim() : '';
  const answers = payload.answers;

  if (!userName) {
    return { error: 'userName is required' };
  }
  if (userName.length > 30) {
    return { error: 'userName must be 30 characters or fewer' };
  }
  if (!Array.isArray(answers)) {
    return { error: 'answers must be an array' };
  }
  if (!Array.isArray(quiz.questions) || answers.length !== quiz.questions.length) {
    return { error: 'answers must match the quiz question count' };
  }

  if (quiz.type === 'personality') {
    const outcomes = quiz.outcomes || {};
    const validOutcomeIds = new Set(Object.keys(outcomes));

    if (typeof payload.outcome !== 'string' || !validOutcomeIds.has(payload.outcome)) {
      return { error: 'outcome must be a valid quiz outcome' };
    }
    if (payload.score !== undefined && payload.score !== null) {
      return { error: 'score is not accepted for personality quizzes' };
    }

    for (let i = 0; i < quiz.questions.length; i += 1) {
      const answer = answers[i];
      const questionAnswers = quiz.questions[i].answers || [];
      const validForQuestion = questionAnswers.some(option => option.outcome === answer);

      if (typeof answer !== 'string' || !validOutcomeIds.has(answer) || !validForQuestion) {
        return { error: `answers[${i}] is not a valid answer outcome` };
      }
    }

    const calculatedOutcome = calculatePersonalityOutcome(answers);
    if (payload.outcome !== calculatedOutcome) {
      return { error: 'outcome does not match submitted answers' };
    }

    return { value: { userName, answers, outcome: calculatedOutcome, score: null } };
  }

  if (quiz.type === 'trivia') {
    if (payload.outcome !== undefined && payload.outcome !== null) {
      return { error: 'outcome is not accepted for trivia quizzes' };
    }

    let calculatedScore = 0;
    for (let i = 0; i < quiz.questions.length; i += 1) {
      const answer = answers[i];
      const question = quiz.questions[i];
      const optionsCount = Array.isArray(question.options) ? question.options.length : 0;

      if (!Number.isInteger(answer) || answer < 0 || answer >= optionsCount) {
        return { error: `answers[${i}] is not a valid option index` };
      }
      if (answer === question.correctIndex) {
        calculatedScore += 1;
      }
    }

    if (!Number.isInteger(payload.score) || payload.score !== calculatedScore) {
      return { error: 'score does not match submitted answers' };
    }

    return { value: { userName, answers, outcome: null, score: calculatedScore } };
  }

  return { error: 'Unsupported quiz type' };
}

// Helper: Load quiz from JSON file
function loadQuiz(quizId) {
  const basePath = path.join(__dirname, '../data/quizzes');
  
  // Try personality folder first
  let quizPath = path.join(basePath, 'personality', `${quizId}.json`);
  if (fs.existsSync(quizPath)) {
    return JSON.parse(fs.readFileSync(quizPath, 'utf-8'));
  }
  
  // Try trivia folder
  quizPath = path.join(basePath, 'trivia', `${quizId}.json`);
  if (fs.existsSync(quizPath)) {
    return JSON.parse(fs.readFileSync(quizPath, 'utf-8'));
  }
  
  return null;
}

// Helper: Get all quizzes
function getAllQuizzes() {
  const basePath = path.join(__dirname, '../data/quizzes');
  const quizzes = [];
  
  ['personality', 'trivia'].forEach(type => {
    const typePath = path.join(basePath, type);
    if (fs.existsSync(typePath)) {
      fs.readdirSync(typePath)
        .filter(f => f.endsWith('.json'))
        .forEach(file => {
          try {
            const quiz = JSON.parse(fs.readFileSync(path.join(typePath, file), 'utf-8'));
            // Get play count from database
            const rows = selectRows('SELECT play_count FROM quizzes WHERE id = ?', [quiz.id]);
            const playCount = rows.length > 0 ? rows[0].play_count || 0 : 0;
            
            quizzes.push({
              id: quiz.id,
              type: quiz.type,
              category: quiz.category,
              title: quiz.title,
              description: quiz.description,
              coverImage: quiz.coverImage,
              questionsCount: quiz.questions?.length || 0,
              playCount: playCount,
              createdAt: quiz.createdAt
            });
          } catch (e) {
            console.error(`Error loading ${file}:`, e);
          }
        });
    }
  });
  
  // Sort by creation date, newest first
  return quizzes.sort((a, b) => new Date(b.createdAt) - new Date(a.createdAt));
}

// ============================================
// API ROUTES
// ============================================

// GET /api/quizzes - List all quizzes
app.get('/api/quizzes', (req, res) => {
  const { type, category } = req.query;
  let quizzes = getAllQuizzes();
  
  if (type) {
    quizzes = quizzes.filter(q => q.type === type);
  }
  if (category) {
    quizzes = quizzes.filter(q => q.category === category);
  }
  
  res.json({ quizzes });
});

// GET /api/quizzes/:id - Get a specific quiz
app.get('/api/quizzes/:id', (req, res) => {
  const quiz = loadQuiz(req.params.id);
  
  if (!quiz) {
    return res.status(404).json({ error: 'Quiz not found' });
  }
  
  res.json(quiz);
});

// POST /api/quizzes/:id/responses - Submit quiz response
app.post('/api/quizzes/:id/responses', (req, res) => {
  const quizId = req.params.id;
  
  const quiz = loadQuiz(quizId);
  if (!quiz) {
    return res.status(404).json({ error: 'Quiz not found' });
  }

  const validation = validateResponsePayload(quiz, req.body || {});
  if (validation.error) {
    return res.status(400).json({ error: validation.error });
  }

  const { userName, answers, outcome, score } = validation.value;
  
  const responseId = generateId();
  const now = new Date().toISOString();
  
  // Insert response
  db.run(
    `INSERT INTO responses (id, quiz_id, user_name, answers, outcome, score, created_at)
     VALUES (?, ?, ?, ?, ?, ?, ?)`,
    [responseId, quizId, userName, JSON.stringify(answers), outcome, score, now]
  );
  
  // Update or insert quiz record and increment play count
  const existing = selectRows('SELECT id FROM quizzes WHERE id = ?', [quizId]);
  if (existing.length > 0) {
    db.run(`UPDATE quizzes SET play_count = play_count + 1 WHERE id = ?`, [quizId]);
  } else {
    db.run(
      `INSERT INTO quizzes (id, type, category, title, play_count, created_at)
       VALUES (?, ?, ?, ?, 1, ?)`,
      [quizId, quiz.type, quiz.category, quiz.title, now]
    );
  }
  
  saveDatabase();
  
  res.json({
    id: responseId,
    message: 'Response saved successfully'
  });
});

// GET /api/quizzes/:id/stats - Get quiz statistics
app.get('/api/quizzes/:id/stats', (req, res) => {
  const quizId = req.params.id;
  
  // Total responses
  const totalRows = selectRows('SELECT COUNT(*) as total FROM responses WHERE quiz_id = ?', [quizId]);
  const total = totalRows.length > 0 ? totalRows[0].total : 0;
  
  // Outcome distribution
  const outcomeRows = selectRows(`
    SELECT outcome, COUNT(*) as count
    FROM responses
    WHERE quiz_id = ? AND outcome IS NOT NULL
    GROUP BY outcome
  `, [quizId]);
  
  const outcomeDistribution = {};
  const outcomePercentages = {};
  outcomeRows.forEach(row => {
    outcomeDistribution[row.outcome] = row.count;
    outcomePercentages[row.outcome] = total > 0 ? Math.round((row.count / total) * 100) : 0;
  });
  
  // Average score
  const scoreRows = selectRows(`
    SELECT AVG(score) as avg_score
    FROM responses
    WHERE quiz_id = ? AND score IS NOT NULL
  `, [quizId]);
  const avgScore = scoreRows.length > 0 && scoreRows[0].avg_score !== null 
    ? Math.round(scoreRows[0].avg_score * 10) / 10 
    : null;
  
  // Score distribution
  const scoreDistRows = selectRows(`
    SELECT score, COUNT(*) as count
    FROM responses
    WHERE quiz_id = ? AND score IS NOT NULL
    GROUP BY score
    ORDER BY score
  `, [quizId]);
  
  const scoreDistribution = {};
  scoreDistRows.forEach(row => {
    scoreDistribution[row.score] = row.count;
  });
  
  res.json({
    totalResponses: total,
    outcomeDistribution,
    outcomePercentages,
    averageScore: avgScore,
    scoreDistribution
  });
});

// GET /api/responses/:id - Get a specific response
app.get('/api/responses/:id', (req, res) => {
  const rows = selectRows(`
    SELECT id, quiz_id, user_name, answers, outcome, score, created_at
    FROM responses WHERE id = ?
  `, [req.params.id]);
  
  if (rows.length === 0) {
    return res.status(404).json({ error: 'Response not found' });
  }
  
  const row = rows[0];
  res.json({
    id: row.id,
    quizId: row.quiz_id,
    userName: row.user_name,
    answers: JSON.parse(row.answers),
    outcome: row.outcome,
    score: row.score,
    createdAt: row.created_at
  });
});

// Serve frontend for all other routes
app.get('*', (req, res) => {
  res.sendFile(path.join(__dirname, '../frontend/index.html'));
});

// Initialize and start server
initDatabase().then(() => {
  app.listen(PORT, () => {
    console.log(`\n🚀 Quiz Platform Server Running!`);
    console.log(`   Local: http://localhost:${PORT}`);
    console.log(`\n📋 API Endpoints:`);
    console.log(`   GET  /api/quizzes          - List all quizzes`);
    console.log(`   GET  /api/quizzes/:id      - Get quiz details`);
    console.log(`   POST /api/quizzes/:id/responses - Submit response`);
    console.log(`   GET  /api/quizzes/:id/stats     - Get quiz stats`);
    console.log(`\n`);
  });
}).catch(err => {
  console.error('Failed to initialize database:', err);
  process.exit(1);
});
