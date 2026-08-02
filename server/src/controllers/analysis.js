const fs = require('fs');
const path = require('path');
const ffmpeg = require('fluent-ffmpeg');
const ffmpegPath = require('ffmpeg-static');
const ytdlp = require('yt-dlp-exec');
const axios = require('axios');
const ExcelJS = require('exceljs');
const OpenAI = require("openai");
const { GoogleGenerativeAI } = require("@google/generative-ai");
const Analysis = require("../models/Analysis");

ffmpeg.setFfmpegPath(ffmpegPath);

// ── Gemini client (reads Gemini_API_KEY from .env) ─────────────────────────
const geminiKey = process.env.Gemini_API_KEY;
if (!geminiKey) console.warn("⚠️  Gemini_API_KEY not set in .env – AI analysis may fail");
const genAI = new GoogleGenerativeAI(geminiKey || "");
const geminiModel = genAI.getGenerativeModel({ model: "gemini-1.5-flash" }); // free: 1500 req/day

// ── Whisper proxy (for audio transcription only) ───────────────────────────
const whisperClient = new OpenAI({
  baseURL: "https://smart-parser-hub.preview.emergentagent.com/api/v1",
  apiKey: "sk-g3f-ojjyAwhHFgYWnjW8gOkpJm17cMZhcv6VHgoUWn2p",
});

// ── Helper: call Gemini with 429 retry ────────────────────────────────────
async function geminiJSON(prompt, retries = 2) {
  for (let attempt = 0; attempt <= retries; attempt++) {
    try {
      const result = await geminiModel.generateContent(prompt);
      let text = result.response.text().trim();
      text = text.replace(/^```json\s*/i, "").replace(/^```\s*/i, "").replace(/\s*```$/i, "").trim();
      return JSON.parse(text);
    } catch (err) {
      const is429 = err.message && (err.message.includes("429") || err.message.includes("quota") || err.message.includes("Too Many"));
      if (is429 && attempt < retries) {
        const waitMs = 65000; // wait 65s then retry
        console.warn(`⏳ Gemini 429 rate limit hit. Waiting ${waitMs / 1000}s before retry ${attempt + 1}/${retries}...`);
        await new Promise(r => setTimeout(r, waitMs));
        continue;
      }
      throw err;
    }
  }
}

// ── Helper: call Gemini text (non-JSON) with 429 retry ─────────────────────
async function geminiText(prompt, retries = 2) {
  for (let attempt = 0; attempt <= retries; attempt++) {
    try {
      const result = await geminiModel.generateContent(prompt);
      return result.response.text();
    } catch (err) {
      const is429 = err.message && (err.message.includes("429") || err.message.includes("quota") || err.message.includes("Too Many"));
      if (is429 && attempt < retries) {
        const waitMs = 65000;
        console.warn(`⏳ Gemini 429. Waiting ${waitMs / 1000}s before retry ${attempt + 1}/${retries}...`);
        await new Promise(r => setTimeout(r, waitMs));
        continue;
      }
      throw err;
    }
  }
}

// ==================== HELPERS ====================

// Check if video has an audio track
async function hasAudioTrack(videoPath) {
  return new Promise((resolve) => {
    ffmpeg.ffprobe(videoPath, (err, metadata) => {
      if (err) return resolve(false);
      const audioStream = (metadata.streams || []).find(
        (s) => s.codec_type === 'audio'
      );
      resolve(!!audioStream);
    });
  });
}

// Extract Audio
function extractAudioFromVideo(videoPath, outAudioPath) {
  return new Promise((resolve, reject) => {
    ffmpeg(videoPath)
      .noVideo()
      .audioCodec('pcm_s16le')
      .format('wav')
      .on('end', () => resolve(outAudioPath))
      .on('error', reject)
      .save(outAudioPath);
  });
}

// Extract Keyframes
function extractKeyframes(videoPath, outFolder, everySeconds = 3) {
  return new Promise((resolve, reject) => {
    if (!fs.existsSync(outFolder)) fs.mkdirSync(outFolder, { recursive: true });
    ffmpeg(videoPath)
      .outputOptions([`-vf fps=1/${everySeconds}`])
      .output(path.join(outFolder, 'frame-%04d.jpg'))
      .on('end', () => {
        const files = fs.readdirSync(outFolder).filter(f => f.startsWith('frame-'));
        resolve(files.map(f => path.join(outFolder, f)));
      })
      .on('error', reject)
      .run();
  });
}



async function downloadIfUrl(videoUrl, destPath) {
  console.log("📥 Downloading:", videoUrl);

  // ✅ Fix Shorts URL
  if (videoUrl.includes("youtube.com/shorts/")) {
    videoUrl = videoUrl.replace("youtube.com/shorts/", "youtube.com/watch?v=");
  }

  const dir = path.dirname(destPath);
  if (!fs.existsSync(dir)) fs.mkdirSync(dir, { recursive: true });

  try {
    await ytdlp(videoUrl, {
      output: destPath.replace(/\.mp4$/, ".%(ext)s"),
      mergeOutputFormat: "mp4",
      format: "bv*+ba/b",
      retries: 5,
      noCheckCertificates: true,
      verbose: true,
      addHeader: [
        "Referer: https://www.youtube.com/",
        "Origin: https://www.youtube.com",
      ],
      userAgent:
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0 Safari/537.36",
      extractorArgs: "youtube:player_client=android", // ✅ Android client avoids SABR issue
    });

    console.log("✅ Download complete!");
    return destPath;
  } catch (error) {
    console.warn("⚠ yt-dlp failed:", error.message);
    console.log("🔁 Trying fallback method...");
    return await fallbackDownload(videoUrl, destPath);
  }
}

async function fallbackDownload(videoUrl, destPath) {
  try {
    // ✅ Try a lightweight online API fallback
    const infoRes = await axios.get(
      `https://api.tikcdn.io/ytdlp?url=${encodeURIComponent(videoUrl)}`
    );

    const downloadLink =
      infoRes.data?.formats?.find((f) => f.mimeType.includes("mp4"))?.url ||
      infoRes.data?.url;

    if (!downloadLink) throw new Error("No valid video URL found.");

    const videoStream = await axios.get(downloadLink, {
      responseType: "arraybuffer",
    });

    fs.writeFileSync(destPath, videoStream.data);
    console.log("✅ Fallback download complete!");
    return destPath;
  } catch (err) {
    console.error("❌ Fallback failed:", err.message);
    throw new Error("YouTube download failed completely. Try another link.");
  }
}



/*
async function downloadIfUrl(videoUrl, destPath) {
  console.log(`📥 Downloading from: ${videoUrl}`);

  await ytdlp(videoUrl, {
    output: destPath,
    format: 'bestvideo+bestaudio/best', // 🔥 Ensures both audio & video
    mergeOutputFormat: 'mp4'            // 🔥 Merge streams into MP4
  });

  console.log(`✅ Download complete: ${destPath}`);
  return destPath;
}*/


// Format seconds to MM:SS
function formatTime(seconds) {
  const mins = Math.floor(seconds / 60);
  const secs = seconds % 60;
  return `${mins}:${secs.toString().padStart(2, '0')}`;
}

// Extract Topics & Entities (Local)
function extractTopicsAndEntities(transcript) {
  if (!transcript || transcript.trim() === '') {
    return { topics: [], entities: [] };
  }

  const words = transcript
    .replace(/[^a-zA-Z0-9\s]/g, '')
    .split(/\s+/)
    .filter((w) => w.length > 3);

  const freq = {};
  words.forEach((w) => {
    const lower = w.toLowerCase();
    freq[lower] = (freq[lower] || 0) + 1;
  });

  const sorted = Object.entries(freq).sort((a, b) => b[1] - a[1]);
  const topics = sorted.slice(0, 5).map(([word]) => word);

  const entities = transcript
    .split(/\s+/)
    .filter((w) => /^[A-Z][a-z]+/.test(w))
    .slice(0, 5);

  return { topics, entities };
}

// Hook and CTA Detection
function findHookAndCTA(transcript, durationSeconds) {
  const sentences = transcript
    .split(/[.!?]/)
    .map(s => s.trim())
    .filter(Boolean);

  let hook = null, hookIndex = -1, hookTiming = '0:00';
  const hookSearchLimit = Math.min(sentences.length, Math.ceil(sentences.length * 0.2));
  for (let i = 0; i < hookSearchLimit; i++) {
    const s = sentences[i];
    if (s.split(/\s+/).length <= 15 && s.length > 10) {
      hook = s; hookIndex = i;
      hookTiming = formatTime(Math.floor((i / sentences.length) * durationSeconds));
      break;
    }
  }
  if (!hook && sentences.length) { hook = sentences[0]; hookIndex = 0; }

  const ctaRegex = /(subscribe|follow|like|comment|buy|download|sign up|click|check out|join|learn more|visit|share)/i;
  let cta = null, ctaIndex = -1, ctaType = 'Follow', ctaTiming = formatTime(durationSeconds);
  const ctaSearchStart = Math.floor(sentences.length * 0.7);
  for (let i = sentences.length - 1; i >= ctaSearchStart; i--) {
    if (ctaRegex.test(sentences[i])) {
      cta = sentences[i]; ctaIndex = i;
      ctaTiming = formatTime(Math.floor((i / sentences.length) * durationSeconds));
      if (/subscribe/i.test(cta)) ctaType = 'Subscribe';
      else if (/follow/i.test(cta)) ctaType = 'Follow';
      else if (/(like|comment)/i.test(cta)) ctaType = 'Engagement';
      else if (/(buy|purchase)/i.test(cta)) ctaType = 'Purchase';
      break;
    }
  }

  return { hook: hook || 'No hook detected', hookIndex, hookTiming, cta: cta || 'No CTA found', ctaIndex, ctaTiming, ctaType, sentences };
}

// Sentiment Analysis via Gemini
async function analyzeSentiment(text) {
  if (!text || text.trim() === '') {
    return { label: 'Neutral', score: 0.5, tones: ['Informative'], primaryEmotion: 'Neutral', feedback: 'No transcript available.' };
  }
  try {
    const prompt = `Analyze the sentiment and emotion of the following video transcript text.
Return ONLY a valid JSON object with exactly these keys (no extra text, no markdown):
{
  "label": "Positive" or "Negative" or "Neutral",
  "score": a float between 0.0 and 1.0 representing confidence,
  "primaryEmotion": dominant emotion (Joy, Sadness, Anger, Fear, Surprise, Motivation, Humor, Confidence, or Neutral),
  "tones": array of 1-3 tone strings (e.g. ["Educational", "Enthusiastic"])
}

Text: "${text.slice(0, 800)}"`;

    const result = await geminiJSON(prompt);
    return {
      label: result.label || 'Neutral',
      score: result.score || 0.5,
      tones: result.tones || ['Informative'],
      primaryEmotion: result.primaryEmotion || 'Neutral',
      feedback: `Sentiment detected as ${result.label || 'Neutral'}.`
    };
  } catch (error) {
    console.error('Gemini sentiment error:', error.message);
    return { label: 'Neutral', score: 0.5, tones: ['Informative'], primaryEmotion: 'Neutral', feedback: 'Default sentiment (Gemini error).' };
  }
}

// AI Suggestions via Gemini
async function generateAISuggestions(transcript, scores, hook, cta) {
  try {
    const prompt = `You are an expert YouTube video marketing coach.
Analyze this video data and return ONLY a valid JSON array of exactly 3 improvement suggestions (no extra text, no markdown).

Data:
- Hook: "${hook}"
- CTA: "${cta}"
- Hook Strength Score: ${scores.hookStrength}/10
- CTA Effectiveness: ${scores.ctaEffectiveness}/10
- Engagement Potential: ${scores.engagementPotential}/10
- Transcript snippet: "${transcript.slice(0, 400)}"

Return format:
[
  { "title": "Short action title", "description": "1-2 sentence actionable tip", "category": "hook" or "cta" or "engagement" or "retention" },
  { "title": "...", "description": "...", "category": "..." },
  { "title": "...", "description": "...", "category": "..." }
]`;

    const result = await geminiModel.generateContent(prompt);
    let text = result.response.text().trim();
    text = text.replace(/^```json\s*/i, "").replace(/^```\s*/i, "").replace(/\s*```$/i, "").trim();
    return JSON.parse(text);
  } catch (err) {
    console.error('Gemini AI suggestions error:', err.message);
    return [
      { title: "Improve Hook", description: "Start with a bold statement or question in the first 3 seconds to grab attention immediately.", category: "hook" },
      { title: "Boost Engagement", description: "Add visual elements or B-roll footage around the 3–5 minute mark to maintain viewer interest.", category: "engagement" },
      { title: "Strengthen CTA", description: "Make your call-to-action more specific and repeat it at the end for higher conversion.", category: "cta" }
    ];
  }
}

// ==================== MAIN FUNCTION ====================
exports.analyzeVideo = async (req, res) => {
  console.log('✅ analyzeVideo called');

  const uploadsDir = path.join(__dirname, '..', '..', 'uploads');
  if (!fs.existsSync(uploadsDir)) fs.mkdirSync(uploadsDir, { recursive: true });

  let localVideoPath = null, tempAudio = null, keyframeDir = null;

  try {
    const videoFile = req.file;
    const videoUrl = req.body.videoUrl || req.body.video_url || null;

    if (!videoFile && !videoUrl) {
      return res.status(400).json({ error: 'Provide uploaded file (field: video) OR videoUrl in body.' });
    }

    let linkAnalysis = null;
    if (videoUrl) {
      console.log('🤖 Sending link to Gemini for analysis...');
      try {
        const linkPrompt = `You are an expert video marketing analyst. Analyze the YouTube video at this URL: ${videoUrl}
Provide a structured analysis including:
1. Estimated core message / topic
2. Target audience
3. Hook strength (what grabs attention in first 5 seconds)
4. Calls to action detected
5. Content quality observations
6. Suggestions for improvement

Be specific and actionable.`;
        linkAnalysis = await retryGemini(linkPrompt);
        console.log('✅ Gemini link analysis complete');
      } catch (e) {
        console.warn('⚠️ Gemini link analysis failed (continuing without it):', e.message?.slice(0, 120));
      }
    }

    if (videoFile) {
      localVideoPath = videoFile.path;
      console.log('📥 Uploaded file:', localVideoPath);
    } else {
      const dlName = `youtube_${Date.now()}.mp4`;
      localVideoPath = path.join(uploadsDir, dlName);
      console.log('🌐 Downloading video from URL...');
      await downloadIfUrl(videoUrl, localVideoPath);
      console.log('✅ Downloaded to', localVideoPath);
    }

    const getDuration = () => new Promise((resolve, reject) => {
      ffmpeg.ffprobe(localVideoPath, (err, metadata) => {
        if (err) return reject(err);
        resolve(metadata.format.duration || 0);
      });
    });
    const durationSeconds = Math.round(await getDuration());
    console.log('⏱ Duration (s):', durationSeconds);

    const audioExists = await hasAudioTrack(localVideoPath);
    let transcript = '';

    if (audioExists) {
      tempAudio = localVideoPath.replace(/\.[^/.]+$/, '') + '.wav';
      console.log('🎧 Extracting audio...');
      await extractAudioFromVideo(localVideoPath, tempAudio);
      console.log('✅ Audio extracted');

      // Try Whisper transcription — non-blocking, fall back to empty transcript
      try {
        console.log('📝 Sending audio to Whisper for transcription...');
        const whisperRes = await whisperClient.audio.transcriptions.create({
          file: fs.createReadStream(tempAudio),
          model: "whisper-1"
        });
        transcript = whisperRes.text || '';
        console.log('✅ Whisper transcription complete, words:', transcript.split(/\s+/).length);
      } catch (whisperErr) {
        console.warn('⚠️ Whisper transcription failed (local analysis only):', whisperErr.message?.slice(0, 100));
        transcript = ''; // continue with empty transcript — scores computed from keywords
      }
    } else {
      console.warn("⚠️ No audio track found, skipping transcription.");
    }

    transcript = transcript.replace(/\s+/g, ' ').trim();

    const { hook, hookTiming, cta, ctaTiming, ctaType, sentences } = findHookAndCTA(transcript, durationSeconds);
    const wordCount = transcript.split(/\s+/).filter(Boolean).length;
    const wpm = durationSeconds ? Math.round((wordCount / durationSeconds) * 60) : 0;

    console.log('🎭 Analyzing sentiment...');
    const sentiment = await analyzeSentiment(transcript);

    const topics = extractTopicsAndEntities(transcript);

    // Placeholder scoring function (implement your own logic)
    // ==================== SMART SCORING SYSTEM ====================

    // Keyword banks (100+)
    const HOOK_KEYWORDS = [
      "listen", "wait", "stop", "imagine", "guess", "you won't believe", "secret", "hack",
      "amazing", "unbelievable", "viral", "crazy", "best ever", "today", "truth", "breaking",
      "challenge", "alert", "must watch", "important", "finally", "hidden", "discover", "how to",
      "learn", "why", "explained", "trick", "tip", "fast", "before you", "did you know", "real story",
      "moment", "caught", "watch till end", "gone wrong", "gone right", "surprise", "epic",
      "legendary", "massive", "next level", "instant", "no one told", "revealed", "story time",
      "life changing", "warning", "confession", "reaction", "crazy fact", "first time", "step by step",
      "tutorial", "secret behind", "don’t skip", "truth about", "make sure", "at last", "pro tip",
      "watch this", "so funny", "you need to see", "try this", "attention", "guaranteed", "exclusive",
      "real talk", "funny", "wait for it", "you won’t guess", "motivational", "emotional", "powerful",
      "explained simply", "in 30 seconds", "part 1", "what happens next", "don’t miss", "everyone should know",
      "instant success", "learned from", "mistake", "behind the scenes", "incredible", "shortcut", "before-after",
      "experiment", "let’s see", "let me show", "quick demo", "proof", "listen carefully", "see yourself",
      "deep truth", "busted", "real example", "fastest", "no clickbait"
    ];

    const CTA_KEYWORDS = [
      "subscribe", "follow", "like", "comment", "share", "save", "buy", "download", "join",
      "click", "watch", "sign up", "order", "check out", "learn more", "support", "link in bio",
      "swipe up", "tap", "visit", "register", "get yours", "start now", "follow me", "stay tuned",
      "don’t miss", "turn on", "enable", "read more", "shop now"
    ];

    // Hook keyword detection
    let hookKeywordMatches = HOOK_KEYWORDS.filter(k =>
      transcript.toLowerCase().includes(k.toLowerCase())
    );
    let hookStrength = Math.min(10, (hookKeywordMatches.length / 10) * 10);

    // CTA keyword detection
    let ctaKeywordMatches = CTA_KEYWORDS.filter(k =>
      transcript.toLowerCase().includes(k.toLowerCase())
    );
    let ctaEffectiveness = Math.min(10, (ctaKeywordMatches.length / 5) * 10);

    // Sentiment and emotion scoring
    // ==================== SENTIMENT & EMOTION SCORING (ENHANCED) ====================

    // Emotion keyword library (200+)
    const EMOTION_KEYWORDS = {
      joy: [
        "happy", "joy", "glad", "delight", "cheerful", "smile", "grateful", "pleased", "content",
        "awesome", "great", "fun", "fantastic", "wonderful", "love", "beautiful", "amazing", "grin",
        "laugh", "excited", "party", "positive", "yay", "wow", "so good", "nice", "pleasant", "peaceful",
        "relaxed", "bright", "playful", "inspired", "thankful", "lovely", "enjoy", "sweet", "kind", "heartwarming"
      ],
      sadness: [
        "sad", "cry", "hurt", "pain", "lost", "lonely", "grief", "upset", "tears", "broken", "sorry",
        "depressed", "miserable", "sorrow", "heartbroken", "disappointed", "missing", "regret", "tired",
        "exhausted", "hopeless", "gone", "tragic", "suffering", "alone", "low", "defeated", "forgotten", "helpless"
      ],
      anger: [
        "angry", "mad", "furious", "rage", "hate", "annoyed", "irritated", "frustrated", "disgusted",
        "shout", "fight", "scream", "offended", "upset", "argue", "hate", "complain", "blame", "revenge",
        "furious", "enraged", "aggressive", "unfair", "disrespect", "offensive", "criticize", "irritating"
      ],
      fear: [
        "afraid", "scared", "terrified", "fear", "nervous", "worried", "anxious", "panic", "shiver",
        "doubt", "hesitant", "unsafe", "risky", "threat", "pressure", "uncomfortable", "fearful", "horror",
        "shock", "creepy", "tension", "frightened", "haunted", "nightmare", "dark", "trouble", "spooky", "alert"
      ],
      surprise: [
        "surprise", "shocked", "unexpected", "wow", "unbelievable", "amazed", "astonished", "what", "crazy",
        "suddenly", "guess what", "out of nowhere", "incredible", "unreal", "mindblown", "unexpectedly", "amazing"
      ],
      disgust: [
        "disgust", "gross", "nasty", "dirty", "hate", "offensive", "repulsive", "yuck", "eww", "horrible",
        "terrible", "bad", "dislike", "ugly", "awful", "unpleasant", "vomit", "stinky", "unacceptable", "annoying"
      ],
      motivation: [
        "motivation", "inspire", "goal", "dream", "success", "achieve", "growth", "believe", "focus", "power",
        "strong", "hope", "discipline", "confidence", "mindset", "determination", "courage", "ambition",
        "hustle", "win", "never give up", "you can", "believe in yourself", "dedication", "journey", "path",
        "overcome", "work hard", "improve", "struggle", "effort", "energy", "leader", "potential", "positive thinking"
      ],
      humor: [
        "funny", "laugh", "lol", "hilarious", "comedy", "joke", "meme", "lmao", "haha", "sarcastic", "silly",
        "roast", "pun", "humor", "giggle", "smirk", "clown", "fun", "entertain", "entertaining", "banter",
        "satire", "troll", "laughing", "lighthearted", "witty", "goofy", "ridiculous", "playful", "funniest"
      ],
      confidence: [
        "confident", "sure", "certain", "bold", "fearless", "powerful", "dominate", "boss", "ready", "capable",
        "leader", "unstoppable", "determined", "focused", "motivated", "assertive", "brave", "strong", "calm", "winning"
      ],
      neutral: [
        "okay", "fine", "maybe", "average", "normal", "casual", "alright", "informative", "discuss", "share",
        "details", "explain", "facts", "tutorial", "lesson", "guide", "process", "example", "demo", "step"
      ]
    };

    // Detect emotion keywords
    function detectDominantEmotion(text) {
      const lower = text.toLowerCase();
      let maxMatches = 0;
      let detectedEmotion = "Neutral";

      for (const [emotion, keywords] of Object.entries(EMOTION_KEYWORDS)) {
        const matches = keywords.filter(k => lower.includes(k.toLowerCase())).length;
        if (matches > maxMatches) {
          maxMatches = matches;
          detectedEmotion = emotion.charAt(0).toUpperCase() + emotion.slice(1);
        }
      }
      return detectedEmotion;
    }

    const detectedEmotion = detectDominantEmotion(transcript);

    // Sentiment score (0–10)
    let sentimentScore =
      sentiment.label === "Positive"
        ? sentiment.score * 10
        : sentiment.label === "Negative"
          ? (1 - sentiment.score) * 5
          : 5;

    // Emotion score logic (based on detected + model)
    let emotionBoost = 0;
    if (["Joy", "Excitement", "Motivation", "Surprise", "Confidence"].includes(detectedEmotion)) emotionBoost = 2;
    if (["Fear", "Disgust", "Sadness"].includes(detectedEmotion)) emotionBoost = -1;

    let emotionScore =
      (["Joy", "Excitement", "Motivation", "Surprise", "Confidence"].includes(sentiment.primaryEmotion))
        ? 8 + Math.random() * 2
        : 5 + emotionBoost;

    emotionScore = Math.min(10, Math.max(0, emotionScore));

    // Combine for stronger realism
    const finalEmotion = detectedEmotion !== "Neutral" ? detectedEmotion : sentiment.primaryEmotion || "Neutral";


    // Speech quality (based on WPM)
    let speechQuality = 7;
    if (wpm > 180) speechQuality = 9;
    else if (wpm > 150) speechQuality = 8;
    else if (wpm < 90) speechQuality = 6;
    else if (wpm < 60) speechQuality = 4;

    // Engagement potential combines all
    let engagementPotential = (
      hookStrength * 0.35 +
      ctaEffectiveness * 0.25 +
      sentimentScore * 0.2 +
      emotionScore * 0.1 +
      speechQuality * 0.1
    ) / 1;

    // Overall score
    let overallScore = (
      hookStrength * 0.3 +
      ctaEffectiveness * 0.2 +
      sentimentScore * 0.2 +
      engagementPotential * 0.2 +
      speechQuality * 0.1
    );

    // Normalize 0–10
    overallScore = Math.min(10, Math.max(0, overallScore));

    // Message feedback
    let message = overallScore >= 8
      ? "🔥 Excellent hook & strong viral potential!"
      : overallScore >= 6
        ? "💡 Good video with room for improvement."
        : "⚠️ Needs better hook and CTA strategy.";

    const scores = {
      overallScore: +overallScore.toFixed(1),
      hookStrength: +hookStrength.toFixed(1),
      ctaEffectiveness: +ctaEffectiveness.toFixed(1),
      engagementPotential: +engagementPotential.toFixed(1),
      speechQuality: +speechQuality.toFixed(1),
      message
    };


    console.log('🤖 Generating AI suggestions with Gemini...');
    const aiSuggestions = await generateAISuggestions(transcript, scores, hook, cta);

    keyframeDir = path.join(uploadsDir, `frames_${Date.now()}`);
    console.log('📸 Extracting keyframes...');
    const frames = await extractKeyframes(localVideoPath, keyframeDir, 3);

    // ==================== GENERATE EXCEL ====================
    const workbook = new ExcelJS.Workbook();
    const sheet = workbook.addWorksheet("Video Analysis");

    // Add Overall Scores
    sheet.addRow(["Overall Score", scores.overallScore.toFixed(1)]);
    sheet.addRow(["Hook Strength", scores.hookStrength.toFixed(1)]);
    sheet.addRow(["CTA Effectiveness", scores.ctaEffectiveness.toFixed(1)]);
    sheet.addRow(["Engagement Potential", scores.engagementPotential.toFixed(1)]);
    sheet.addRow(["Message", scores.overallScore >= 8 ? "Strong viral potential!" :
      scores.overallScore >= 6 ? "Good video with room for improvement." : "Needs optimization."]);
    sheet.addRow([]);

    // Hook & CTA
    sheet.addRow(["Hook", hook]);
    sheet.addRow(["Hook Timing", hookTiming]);
    sheet.addRow(["CTA", cta]);
    sheet.addRow(["CTA Timing", ctaTiming]);
    sheet.addRow(["CTA Type", ctaType]);
    sheet.addRow([]);

    // Sentiment
    sheet.addRow(["Sentiment Label", sentiment.label]);
    sheet.addRow(["Sentiment Score", sentiment.score]);
    sheet.addRow(["Primary Emotion", sentiment.primaryEmotion]);
    sheet.addRow(["Tones", sentiment.tones.join(", ")]);
    sheet.addRow([]);

    // Transcript
    sheet.addRow(["Duration", formatTime(durationSeconds)]);
    sheet.addRow(["Word Count", wordCount]);
    sheet.addRow(["WPM", wpm]);
    sheet.addRow(["Transcript Snippet", transcript.slice(0, 150)]);
    sheet.addRow([]);

    // Topics & Entities
    sheet.addRow(["Top Topics", topics.topics.join(", ")]);
    sheet.addRow(["Entities", topics.entities.join(", ")]);
    sheet.addRow([]);

    // Meta
    sheet.addRow(["Video Source", videoUrl || path.basename(localVideoPath)]);
    sheet.addRow(["Frames Extracted", frames.length]);
    sheet.addRow(["Processing Time", new Date().toISOString()]);

    // Save Excel file
    const excelPath = path.join(uploadsDir, `analysis_${Date.now()}.xlsx`);
    await workbook.xlsx.writeFile(excelPath);
    console.log("📊 Excel report saved:", excelPath);


    // Save to Database
    let savedAnalysis = null;
    try {
      savedAnalysis = await Analysis.create({
        videoSource: videoUrl || (videoFile ? videoFile.originalname : path.basename(localVideoPath)),
        videoType: videoUrl ? (videoUrl.includes("youtube.com") || videoUrl.includes("youtu.be") ? 'youtube' : 'link') : 'upload',
        duration: formatTime(durationSeconds),
        fileSize: videoFile ? videoFile.size : 0,

        overallScore: +scores.overallScore.toFixed(1),
        hookStrength: +scores.hookStrength.toFixed(1),
        ctaEffectiveness: +scores.ctaEffectiveness.toFixed(1),
        engagementPotential: +scores.engagementPotential.toFixed(1),
        speechQuality: +scores.speechQuality.toFixed(1),

        hookStrength100: Math.round(scores.hookStrength * 10),
        ctaEffectiveness100: Math.round(scores.ctaEffectiveness * 10),
        engagementPotential100: Math.round(scores.engagementPotential * 10),
        retention100: Math.round(scores.speechQuality * 10),
        overallScore100: Math.round(scores.overallScore * 10),

        hookText: hook,
        hookTiming: hookTiming,
        ctaText: cta,
        ctaTiming: ctaTiming,
        ctaType: ctaType,

        sentimentLabel: sentiment.label,
        sentimentScore: sentiment.score,
        primaryEmotion: sentiment.primaryEmotion,
        tones: sentiment.tones || [],

        wordCount: wordCount,
        wpm: `${wpm} WPM`,
        transcript: transcript,

        topics: topics.topics || [],
        entities: topics.entities || [],

        aiSuggestions: aiSuggestions || [],
        linkAnalysis: linkAnalysis || '',

        status: 'completed'
      });
      console.log('✅ Analysis saved to DB with ID:', savedAnalysis._id);
    } catch (dbErr) {
      console.error('⚠️ DB Save failed:', dbErr.message);
    }

    res.json({
      _id: savedAnalysis ? savedAnalysis._id : null,
      id: savedAnalysis ? savedAnalysis._id : null,
      overall: {
        score: +scores.overallScore.toFixed(1),
        hookStrength: +scores.hookStrength.toFixed(1),
        ctaEffectiveness: +scores.ctaEffectiveness.toFixed(1),
        engagementPotential: +scores.engagementPotential.toFixed(1),
        message: scores.overallScore >= 8 ? 'Strong viral potential!' :
          scores.overallScore >= 6 ? 'Good video with room for improvement.' : 'Needs optimization.'
      },
      hook: { text: hook, timing: hookTiming },
      cta: { text: cta, placement: ctaTiming, type: ctaType },
      sentiment,
      transcript: { duration: formatTime(durationSeconds), words: wordCount, wpm: `${wpm} WPM`, snippet: transcript.slice(0, 150) },
      topics,
      meta: { videoSource: videoUrl || path.basename(localVideoPath), framesExtracted: frames.length, processingTime: new Date().toISOString() },
      linkAnalysis: linkAnalysis,
      aiSuggestions: aiSuggestions
    });

  } catch (err) {
    console.error('❌ Analysis Error:', err.message || err);
    res.status(500).json({ success: false, error: err.message || err.toString() });
  } finally {
    try { if (tempAudio && fs.existsSync(tempAudio)) fs.unlinkSync(tempAudio); } catch (e) { }
    try { if (keyframeDir && fs.existsSync(keyframeDir)) fs.rmSync(keyframeDir, { recursive: true, force: true }); } catch (e) { }
    // Clean up downloaded YouTube videos to save server disk space
    try {
      if (videoUrl && localVideoPath && fs.existsSync(localVideoPath)) {
        fs.unlinkSync(localVideoPath);
      }
    } catch (e) { }
  }
};

// GET /api/analyses -> List all analyses
exports.getAnalyses = async (req, res) => {
  try {
    const limit = parseInt(req.query.limit) || 20;
    const analyses = await Analysis.find({})
      .sort({ createdAt: -1 })
      .limit(limit);
    
    res.json({ success: true, count: analyses.length, data: analyses });
  } catch (err) {
    console.error("Error fetching analyses:", err);
    res.status(500).json({ success: false, error: err.message });
  }
};

// GET /api/analyses/:id -> Get single analysis by ID
exports.getAnalysisById = async (req, res) => {
  try {
    const analysis = await Analysis.findById(req.params.id);
    if (!analysis) {
      return res.status(404).json({ success: false, error: "Analysis not found" });
    }
    
    // Format response to match expected frontend structure for Results page
    res.json({
      _id: analysis._id,
      id: analysis._id,
      status: analysis.status,
      video: {
        title: analysis.videoSource,
        source: analysis.videoSource,
        type: analysis.videoType,
        duration: analysis.duration,
      },
      summary: {
        summary: analysis.linkAnalysis || `Analysis completed for ${analysis.videoSource}. Overall Hook score is ${analysis.overallScore100 || Math.round(analysis.overallScore * 10)}/100.`
      },
      scores: {
        overall: analysis.overallScore,
        overall100: analysis.overallScore100 || Math.round(analysis.overallScore * 10),
        hook: analysis.hookStrength,
        hook100: analysis.hookStrength100 || Math.round(analysis.hookStrength * 10),
        cta: analysis.ctaEffectiveness,
        cta100: analysis.ctaEffectiveness100 || Math.round(analysis.ctaEffectiveness * 10),
        engagement: analysis.engagementPotential,
        engagement100: analysis.engagementPotential100 || Math.round(analysis.engagementPotential * 10),
        speech: analysis.speechQuality,
        retention100: analysis.retention100 || Math.round(analysis.speechQuality * 10),
        pacing: analysis.speechQuality,
        clarity: Math.round((analysis.hookStrength + analysis.speechQuality) / 2)
      },
      hooks: {
        text: analysis.hookText,
        timing: analysis.hookTiming,
        strength: analysis.hookStrength
      },
      cta: {
        text: analysis.ctaText,
        placement: analysis.ctaTiming,
        type: analysis.ctaType,
        effectiveness: analysis.ctaEffectiveness
      },
      sentiment: {
        label: analysis.sentimentLabel,
        score: analysis.sentimentScore,
        primaryEmotion: analysis.primaryEmotion,
        tones: analysis.tones
      },
      transcript: {
        duration: analysis.duration,
        words: analysis.wordCount,
        wpm: analysis.wpm,
        snippet: analysis.transcript ? analysis.transcript.slice(0, 200) : '',
        full: analysis.transcript
      },
      topics: {
        topics: analysis.topics,
        entities: analysis.entities
      },
      recommendations: analysis.aiSuggestions,
      aiSuggestions: analysis.aiSuggestions,
      createdAt: analysis.createdAt
    });
  } catch (err) {
    console.error("Error fetching analysis by ID:", err);
    res.status(500).json({ success: false, error: err.message });
  }
};
