const { simpleGenScript } = require('../services/simpleNLP');

exports.generateScript = async (req, res) => {
  const { objective, tone, productName, benefits, audience, platform } = req.body;

  const productInfo = `${productName}.\nBenefits:\n${benefits}\nAudience: ${audience}\nPlatform: ${platform}`;
 console.log("🟢 Generating script for:", { objective, tone, productInfo });
  try {
    const script = await simpleGenScript(objective, tone, productInfo);

    if (!script || typeof script !== 'string' || script.trim() === '') {
      return res.status(500).json({ error: "Script generation failed – empty result." });
    }
     console.log("✅ Script generated:", script.slice(0, 100), '...');

    res.json({ script });
  } catch (error) {
    console.error("Script generation error:", error);
    res.status(500).json({ error: "Script generation failed" });
  }
};
