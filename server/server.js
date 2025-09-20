// server.js
const express = require("express");
const mongoose = require("mongoose");
const cors = require("cors");
const dotenv = require("dotenv");
const http = require("http");
const multer = require("multer");
const path = require("path");
const { Server } = require("socket.io");

dotenv.config();

const app = express();
const server = http.createServer(app);
const io = new Server(server, { cors: { origin: "*" } });

// Middleware
app.use(express.json());
app.use(express.urlencoded({ extended: true }));
app.use(cors({
  origin: "http://localhost:5173",
  credentials: true
}));

// File Upload Setup
const upload = multer({ dest: "uploads/" });

// Static Files
app.use("/uploads", express.static(path.join(__dirname, "uploads")));
app.use("/reports", express.static("reports"));

// Routes
const authRoutes = require("./routes/authRoutes");
const analysisRoutes = require("./routes/analyzeRoutes");
const scriptGen = require("./controllers/scriptGen");
const activity = require("./controllers/activity");
const analysisExcelRoutes = require("./routes/analysisExcelRoutes");
const profileRoutes = require("./routes/profileRoute");


app.use("/api/profile", profileRoutes);
app.use("/api/excel", analysisExcelRoutes);
app.use("/api/auth", authRoutes);   
app.use("/api", analysisRoutes);
app.post("/api/generate-script", scriptGen.generateScript);
app.get("/api/recent-activity", activity.getRecentActivity);

// Health Check
app.get("/api/ping", (_, res) => res.json({ ping: "pong" }));
app.get("/", (_, res) => res.send("🎸 Auth System & Hook AI Server Running"));

// ==========================
// 🔥 SOCKET.IO Integration
// ==========================
const { analyzeVideo } = require("./controllers/analysis");

io.on("connection", (socket) => {
  console.log("🔌 Client connected");

  socket.on("startVideoAnalysis", async (filename) => {
    console.log(`🎥 Start processing: ${filename}`);
    const filePath = path.join(__dirname, "uploads", filename);

    try {
      // Send live progress
      socket.emit("progress", { step: "starting", message: "Processing started..." });

      const report = await analyzeVideo(filePath, (step, message) => {
        socket.emit("progress", { step, message });
      });

      socket.emit("progress", { step: "done", message: "Processing complete", data: report });
    } catch (err) {
      console.error(err);
      socket.emit("progress", { step: "error", message: err.message });
    }
  });

  socket.on("disconnect", () => console.log("❌ Client disconnected"));
});

// ==========================
// MongoDB Connection
// ==========================
mongoose
  .connect(process.env.MONGO_URI)
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
