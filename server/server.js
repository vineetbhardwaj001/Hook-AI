const express = require("express");
const mongoose = require("mongoose");
const cors = require("cors");
const dotenv = require("dotenv");
const http = require("http");
const path = require("path");

dotenv.config();

const app = express();
const server = http.createServer(app);

app.use(express.json());
app.use(express.urlencoded({ extended: true }));
app.use(cors({
  origin: "https://hook-ai-henna.vercel.app" /*"https://hook-ai-henna.vercel.app"*/,
  credentials: true
}));

// Serve static files
app.use('/uploads', express.static(path.join(__dirname, 'uploads')));

// ROUTES
const authRoutes = require("./routes/authRoutes");
const analysisRoutes = require("./routes/analyzeRoutes");
const scriptGen = require("./controllers/scriptGen");
const activity = require("./controllers/activity");

app.use("/api/auth", authRoutes);
app.use("/api", analysisRoutes); // ✅ /api/analysis here
app.post("/api/generate-script", scriptGen.generateScript);
app.get("/api/recent-activity", activity.getRecentActivity);

app.get("/api/ping", (_, res) => res.json({ ping: "pong" }));
app.get("/", (_, res) => res.send("🎸 Auth System & Hook AI Server Running"));

mongoose
  .connect(process.env.MONGO_URI, {})
  .then(() => {
    console.log("✅ MongoDB Connected");
    const PORT = process.env.PORT || 3000;
    server.listen(PORT, () => {
      console.log(`🚀 Server running on http://localhost:${PORT}`);
    });
  })
  .catch((err) => console.error("❌ MongoDB connection failed:", err));


/*const express = require("express");
const mongoose = require("mongoose");
const cors = require("cors");
const dotenv = require("dotenv");
const http = require("http");
const multer = require('multer');
const path = require("path");

// Load environment variables from .env
dotenv.config();

const app = express();
const server = http.createServer(app);

// Middlewares
app.use(express.json());
app.use(express.urlencoded({ extended: true }));
app.use(cors({
  origin: "http://localhost:5173",  // Change to frontend domain in production
  credentials: true
}));


const upload = multer({ dest: "uploads/" });


// ROUTES & CONTROLLERS

const authRoutes = require("./routes/authRoutes");
const analysis = require('./controllers/analysis');
const scriptGen = require('./controllers/scriptGen');
const activity = require('./controllers/activity');

// --- Auth Routes ---
app.use("/api/auth", authRoutes);
// Serve static files from uploads
app.use('/uploads', express.static(path.join(__dirname, 'uploads')));
app.post('/api/analysis', upload.single('videoFile'), (req, res) => {
  // Access the file using req.file
  // Access other form fields using req.body
  console.log(req.file);
  console.log(req.body);
  // ... server-side logic to process the file and data
  res.status(200).json({ message: 'Analysis successful' });
});

app.use('/reports', express.static('reports')); // Serve Excel downloads
// --- Hook AI Routes ---
//app.use("/api/video", require("./routes/videoRoutes"));
app.use('/api', require('./routes/analyzeRoutes')); // ✅ gives /api/analysis

app.post('/api/analysis', upload.single('video'), analysis.analyzeVideo);
app.post('/api/generate-script', scriptGen.generateScript);
app.get('/api/recent-activity', activity.getRecentActivity);

// --- Health Check ---
app.get("/api/ping", (_, res) => res.json({ ping: "pong" }));

// --- Home Route ---
app.get("/", (req, res) => {
  res.send("🎸 Auth System & Hook AI Server Running");
});

// ==========================
// MongoDB Connection & Boot
// ==========================
mongoose
  .connect(process.env.MONGO_URI, {})
  .then(() => {
    console.log("✅ MongoDB Connected");
    const PORT = process.env.PORT || 8000;
    server.listen(PORT, () => {
      console.log(`🚀 Server running on http://localhost:${PORT}`);
    });
  })
  .catch((err) => console.error("❌ MongoDB connection failed:", err));*/
