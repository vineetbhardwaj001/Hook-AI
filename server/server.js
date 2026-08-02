// Set UV Threadpool size for high concurrent cryptography and file operations
process.env.UV_THREADPOOL_SIZE = 128;

const express = require("express");
const mongoose = require("mongoose");
const cors = require("cors");
const dotenv = require("dotenv");
const http = require("http");
const multer = require("multer");
const path = require("path");
const { Server } = require("socket.io");
const helmet = require("helmet");
const rateLimit = require("express-rate-limit");

dotenv.config();

const app = express();
const server = http.createServer(app);
const io = new Server(server, { cors: { origin: "*" } });

// Basic Security & Headers
app.use(helmet({
  crossOriginResourcePolicy: false, // Allow loading media from static folders
}));

// API Rate Limiting to prevent DDoS and brute-force
const apiLimiter = rateLimit({
  windowMs: 15 * 60 * 1000, // 15 minutes
  max: 200, // Limit each IP to 200 requests per windowMs
  message: { error: "Too many requests from this IP, please try again later." },
  standardHeaders: true,
  legacyHeaders: false,
});
app.use("/api/", apiLimiter);

// Middleware
app.use(express.json());
app.use(express.urlencoded({ extended: true }));
app.use(cors({
  origin: "http://localhost:5173" || "https://new-hook.vercel.app/",
  credentials: true
}));

// File Upload Setup
const upload = multer({ dest: "uploads/" });

// Static Files
app.use("/uploads", express.static(path.join(__dirname, "uploads")));
app.use("/reports", express.static("reports"));

// Restructured Routes
const authRoutes = require("./src/routes/authRoutes");
const analysisRoutes = require("./src/routes/analyzeRoutes");
const scriptGen = require("./src/controllers/scriptGen");
const activity = require("./src/controllers/activity");
const analysisExcelRoutes = require("./src/routes/analysisExcelRoutes");
const profileRoutes = require("./src/routes/profileRoute");

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
const { analyzeVideo } = require("./src/controllers/analysis");

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

const PORT = process.env.PORT || 3000;
server.listen(PORT, () => {
  console.log(`🚀 Server running on http://localhost:${PORT}`);
});

mongoose
  .connect(process.env.MONGO_URI || 'mongodb+srv://bhar-990:wB7PcnEz8sB9t4jZ@cluster0.tiyilrz.mongodb.net/hook?retryWrites=true&w=majority&appName=Cluster0', {
    maxPoolSize: 100, // Handle up to 100 concurrent DB queries/connections
  })
  .then(() => {
    console.log("✅ MongoDB Connected");
  })
  .catch((err) => {
    console.error("❌ MongoDB connection failed on boot:", err.message || err);
  });

// Global Exception Handlers to keep the server running in case of unhandled errors
process.on("uncaughtException", (err) => {
  console.error("🔥 Global Uncaught Exception:", err);
});
process.on("unhandledRejection", (reason, promise) => {
  console.error("🔥 Global Unhandled Rejection at:", promise, "reason:", reason);
});

