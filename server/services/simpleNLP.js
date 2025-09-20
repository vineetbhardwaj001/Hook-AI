const { GoogleGenerativeAI } = require("@google/generative-ai");

const genAI = new GoogleGenerativeAI(process.env.GEMINI_API_KEY);

// Gemini model choose karna hai (latest: gemini-1.5-pro ya gemini-1.5-flash)
const model = genAI.getGenerativeModel({ model: "gemini-1.5-pro" });

async function simpleGenScript(objective, tone, productInfo) {
  try {
    const prompt = `
      Objective: ${objective}
      Tone: ${tone}
      Product Info:
      ${productInfo}

      Write a short, engaging video script for ${objective} with a ${tone} tone.
      Keep it concise, catchy, and optimized for social media hooks.
    `;

    const result = await model.generateContent(prompt);
    const response = result.response.text();

    return response;
  } catch (err) {
    console.error("Error generating script:", err);
    return null;
  }
}

module.exports = { simpleGenScript };
