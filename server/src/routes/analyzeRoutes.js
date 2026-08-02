const express = require("express");
const router = express.Router();
const multer = require("multer");
const analysisController = require("../controllers/analysis");

// Multer config (file uploads ke liye)
const upload = multer({ dest: "uploads/" });

// ✅ POST /api/analysis
router.post("/analysis", upload.single("video"), analysisController.analyzeVideo);

// ✅ GET /api/analyses
router.get("/analyses", analysisController.getAnalyses);

// ✅ GET /api/analyses/:id
router.get("/analyses/:id", analysisController.getAnalysisById);

module.exports = router;
