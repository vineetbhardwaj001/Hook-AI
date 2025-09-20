const express = require("express");
const multer = require("multer");
const path = require("path");
const fs = require("fs");
const ExcelJS = require("exceljs");
const { simpleGenScript } = require("../services/simpleNLP");

const router = express.Router();

// Multer setup
const upload = multer({ dest: "uploads/" });

// POST → /api/analyze (upload excel + generate script)
router.post("/analyze", upload.single("file"), async (req, res) => {
  try {
    if (!req.file) {
      return res.status(400).json({ error: "No Excel file uploaded" });
    }

    // ✅ Step 1: Read Excel file
    const workbook = new ExcelJS.Workbook();
    await workbook.xlsx.readFile(req.file.path);
    const sheet = workbook.worksheets[0];

    // ✅ Step 2: Extract values (assume row-wise format)
    const extracted = {
      hook: sheet.getCell("B2").value, // example (depends on sheet format)
      hookTiming: sheet.getCell("B3").value,
      cta: sheet.getCell("B4").value,
      ctaTiming: sheet.getCell("B5").value,
      tone: sheet.getCell("B6").value,
      animations: sheet.getCell("B7").value,
      objective: sheet.getCell("B8").value,
      productName: sheet.getCell("B9").value,
      benefits: sheet.getCell("B10").value,
      audience: sheet.getCell("B11").value,
      platform: sheet.getCell("B12").value,
    };

    console.log("📊 Extracted from Excel:", extracted);

    // ✅ Step 3: Create product info prompt
    const productInfo = `${extracted.productName}.
Benefits:
${extracted.benefits}
Audience: ${extracted.audience}
Platform: ${extracted.platform}
Tone: ${extracted.tone}
Hook: ${extracted.hook} (timing ${extracted.hookTiming})
CTA: ${extracted.cta} (timing ${extracted.ctaTiming})
Animations: ${extracted.animations}`;

    // ✅ Step 4: Call script generator
    const script = await simpleGenScript(
      extracted.objective,
      extracted.tone,
      productInfo
    );

    if (!script || typeof script !== "string" || script.trim() === "") {
      return res
        .status(500)
        .json({ error: "Script generation failed – empty result." });
    }

    console.log("✅ Generated script:", script.slice(0, 80), "...");

    res.json({ success: true, extracted, script });
  } catch (error) {
    console.error("❌ Analysis error:", error);
    res.status(500).json({ error: "Excel analysis or script generation failed" });
  } finally {
    // cleanup temp file
    if (req.file && fs.existsSync(req.file.path)) {
      fs.unlinkSync(req.file.path);
    }
  }
});

module.exports = router;
