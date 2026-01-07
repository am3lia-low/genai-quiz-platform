const express = require('express');
const cors = require('cors');
const path = require('path');
const fs = require('fs');
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
  return Math.random().toString(36).substring(2, 10);
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
            const stmt = db.prepare('SELECT play_count FROM quizzes WHERE id = ?');
            stmt.bind([quiz.id]);
            let playCount = 0;
            if (stmt.step()) {
              playCount = stmt.getAsObject().play_count || 0;
            }
            stmt.free();
            
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
  const { userName, answers, outcome, score } = req.body;
  
  if (!userName || !answers) {
    return res.status(400).json({ error: 'userName and answers are required' });
  }
  
  const quiz = loadQuiz(quizId);
  if (!quiz) {
    return res.status(404).json({ error: 'Quiz not found' });
  }
  
  const responseId = generateId();
  const now = new Date().toISOString();
  
  // Insert response
  db.run(
    `INSERT INTO responses (id, quiz_id, user_name, answers, outcome, score, created_at)
     VALUES (?, ?, ?, ?, ?, ?, ?)`,
    [responseId, quizId, userName, JSON.stringify(answers), outcome, score, now]
  );
  
  // Update or insert quiz record and increment play count
  const existing = db.exec(`SELECT id FROM quizzes WHERE id = '${quizId}'`);
  if (existing.length > 0 && existing[0].values.length > 0) {
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
  const totalResult = db.exec(`SELECT COUNT(*) as total FROM responses WHERE quiz_id = '${quizId}'`);
  const total = totalResult.length > 0 ? totalResult[0].values[0][0] : 0;
  
  // Outcome distribution
  const outcomeResult = db.exec(`
    SELECT outcome, COUNT(*) as count
    FROM responses
    WHERE quiz_id = '${quizId}' AND outcome IS NOT NULL
    GROUP BY outcome
  `);
  
  const outcomeDistribution = {};
  const outcomePercentages = {};
  if (outcomeResult.length > 0) {
    outcomeResult[0].values.forEach(row => {
      const [outcome, count] = row;
      outcomeDistribution[outcome] = count;
      outcomePercentages[outcome] = total > 0 ? Math.round((count / total) * 100) : 0;
    });
  }
  
  // Average score
  const scoreResult = db.exec(`
    SELECT AVG(score) as avg_score
    FROM responses
    WHERE quiz_id = '${quizId}' AND score IS NOT NULL
  `);
  const avgScore = scoreResult.length > 0 && scoreResult[0].values[0][0] !== null 
    ? Math.round(scoreResult[0].values[0][0] * 10) / 10 
    : null;
  
  // Score distribution
  const scoreDistResult = db.exec(`
    SELECT score, COUNT(*) as count
    FROM responses
    WHERE quiz_id = '${quizId}' AND score IS NOT NULL
    GROUP BY score
    ORDER BY score
  `);
  
  const scoreDistribution = {};
  if (scoreDistResult.length > 0) {
    scoreDistResult[0].values.forEach(row => {
      scoreDistribution[row[0]] = row[1];
    });
  }
  
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
  const result = db.exec(`
    SELECT id, quiz_id, user_name, answers, outcome, score, created_at
    FROM responses WHERE id = '${req.params.id}'
  `);
  
  if (result.length === 0 || result[0].values.length === 0) {
    return res.status(404).json({ error: 'Response not found' });
  }
  
  const row = result[0].values[0];
  res.json({
    id: row[0],
    quizId: row[1],
    userName: row[2],
    answers: JSON.parse(row[3]),
    outcome: row[4],
    score: row[5],
    createdAt: row[6]
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
