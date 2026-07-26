const express = require("express");
const router = express.Router();
const multer = require("multer");
const analysisController = require("../controllers/analysis");

// Multer config (file uploads ke liye)
const upload = multer({ dest: "uploads/" });

// ✅ POST /api/analysis
// Agar video file upload ho rahi hai → `upload.single("video")`
// Agar sirf URL send kar rahe ho → req.body se handle hoga
router.post("/analysis", upload.single("video"), analysisController.analyzeVideo);

module.exports = router;
