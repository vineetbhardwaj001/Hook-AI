const OpenAI = require("openai");

const client = new OpenAI({
  baseURL: "https://smart-parser-hub.preview.emergentagent.com/api/v1",
  apiKey: "sk-g3f-ojjyAwhHFgYWnjW8gOkpJm17cMZhcv6VHgoUWn2p",
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

    const resp = await client.chat.completions.create({
      model: "gemini-3-flash",
      messages: [
        { role: "system", content: "You are a helpful assistant." },
        { role: "user",   content: prompt },
      ],
    });

    return resp.choices[0].message.content;
  } catch (err) {
    console.error("Error generating script:", err);
    return null;
  }
}

module.exports = { simpleGenScript };
