const OpenAI = require("openai");

const client = new OpenAI({
  baseURL: "https://router.huggingface.co/v1",
  apiKey: process.env.HF_TOKEN,
});

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

    const chatCompletion = await client.chat.completions.create({
      model: "openai/gpt-oss-120b",
      messages: [{ role: "user", content: prompt }],
    });

    return chatCompletion.choices[0].message.content;
  } catch (err) {
    console.error("Error generating script:", err);
    return null;
  }
}

module.exports = { simpleGenScript };