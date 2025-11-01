const fs = require('fs');
const path = require('path');
const ffmpeg = require('fluent-ffmpeg');
const ffmpegPath = require('ffmpeg-static');
const ytdlp = require('yt-dlp-exec');
const axios = require('axios');
const ExcelJS = require('exceljs');

ffmpeg.setFfmpegPath(ffmpegPath);

const HF_TOKEN = process.env.HF_TOKEN;
if (!HF_TOKEN) {
  console.error('⚠️ HF_TOKEN not set in env! Hugging Face API may fail.');
}

const HF_WHISPER = 'openai/whisper-large-v3';
const HF_SENTIMENT = 'distilbert-base-uncased-finetuned-sst-2-english';
const HF_EMOTION = 'j-hartmann/emotion-english-distilroberta-base';

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

// Hugging Face Binary Inference
async function hfBinaryInference(model, buffer, contentType, accept = 'application/json') {
  const url = `https://api-inference.huggingface.co/models/${model}`;
  const res = await axios.post(url, buffer, {
    headers: {
      Authorization: `Bearer ${HF_TOKEN}`,
      'Content-Type': contentType,
      Accept: accept
    },
    responseType: 'json',
    timeout: 600000
  });
  return res.data;
}

// Hugging Face Text Inference
async function hfTextInference(model, inputs) {
  const url = `https://api-inference.huggingface.co/models/${model}`;
  const res = await axios.post(url, { inputs }, {
    headers: {
      Authorization: `Bearer ${HF_TOKEN}`,
      'Content-Type': 'application/json',
      Accept: 'application/json'
    },
    timeout: 600000
  });
  return res.data;
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

 const downloadIfUrl = (url, output) => {
  return new Promise((resolve, reject) => {
    const ytdlp = require('yt-dlp-exec');

    ytdlp(url, {
      output,
      mergeOutputFormat: 'mp4',
      format: "bv*[ext=mp4][height<=1080]+ba[ext=m4a]/bv*+?ba/best[ext=mp4]/best",
      concurrentFragments: 1,
      retries: 10,
      retrySleep: 3,
      throttledRate: "100K",
      // ✅ New safe extractor – removes deprecated players
      extractorArgs: "youtube:player-client=web,web_embedded,tv",
      // ✅ removed deprecated --no-call-home
      noCheckCertificates: true,
      // ✅ option: avoid 429 Too Many Requests
      // cookies: "/opt/render/project/src/server/cookies.txt"
    })
      .then(() => resolve())
      .catch((err) => reject(err));
  });
};


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

// Sentiment Analysis
async function analyzeSentiment(text) {
  if (!text || text.trim() === '') {
    return {
      label: 'Neutral',
      score: 0.5,
      tones: ['Informative'],
      primaryEmotion: 'Neutral',
      feedback: 'No transcript available, using default sentiment.'
    };
  }

  try {
    const sentimentResult = await hfTextInference(HF_SENTIMENT, text);
    const emotionResult = await hfTextInference(HF_EMOTION, text);

    let sentiment = { label: 'Neutral', score: 0.5 };
    if (sentimentResult && sentimentResult[0]) {
      const top = sentimentResult[0];
      sentiment = {
        label: top.label === 'POSITIVE' ? 'Positive' : top.label === 'NEGATIVE' ? 'Negative' : 'Neutral',
        score: top.score
      };
    }

    let primaryEmotion = 'Neutral';
    if (emotionResult && emotionResult[0]) {
      primaryEmotion = emotionResult[0].label.charAt(0).toUpperCase() + emotionResult[0].label.slice(1);
    }

    const tones = [];
    if (/learn|teach|explain|understand|knowledge/i.test(text)) tones.push('Educational');
    if (/amazing|awesome|incredible|fantastic|excited/i.test(text)) tones.push('Enthusiastic');
    if (/funny|hilarious|joke|laugh/i.test(text)) tones.push('Humorous');
    if (/professional|business|strategy/i.test(text)) tones.push('Professional');

    if (!tones.length) tones.push(sentiment.label === 'Positive' ? 'Positive' : 'Informative');

    return {
      label: sentiment.label,
      score: sentiment.score,
      tones,
      primaryEmotion,
      feedback: `Sentiment detected as ${sentiment.label}.`
    };
  } catch (error) {
    console.error('Sentiment analysis error:', error);
    return {
      label: 'Neutral',
      score: 0.5,
      tones: ['Informative'],
      primaryEmotion: 'Neutral',
      feedback: 'Default sentiment due to error.'
    };
  }
}

// ==================== MAIN FUNCTION ====================
exports.analyzeVideo = async (req, res) => {
  console.log('✅ analyzeVideo called');

  const uploadsDir = path.join(__dirname, '..', 'uploads');
  if (!fs.existsSync(uploadsDir)) fs.mkdirSync(uploadsDir, { recursive: true });

  let localVideoPath = null, tempAudio = null, keyframeDir = null;

  try {
    const videoFile = req.file;
    const videoUrl = req.body.videoUrl || req.body.video_url || null;

    if (!videoFile && !videoUrl) {
      return res.status(400).json({ error: 'Provide uploaded file (field: video) OR videoUrl in body.' });
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

      const audioBuffer = fs.readFileSync(tempAudio);
      console.log('📝 Sending to Whisper...');
      const whisperRes = await axios.post(
        `https://api-inference.huggingface.co/models/${HF_WHISPER}`,
        audioBuffer,
        { headers: { Authorization: `Bearer ${HF_TOKEN}`, 'Content-Type': 'audio/wav', Accept: 'application/json' }, timeout: 600000 }
      );
      transcript = whisperRes.data?.text || whisperRes.data?.transcription || '';
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
    const scores = {
      overallScore: 7.5,
      hookStrength: 8.0,
      ctaEffectiveness: 6.5,
      engagementPotential: 7.0
    };

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


    res.json({
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
      meta: { videoSource: videoUrl || path.basename(localVideoPath), framesExtracted: frames.length, processingTime: new Date().toISOString() }
    });

  } catch (err) {
    console.error('❌ Analysis Error:', err.message || err);
    res.status(500).json({ success: false, error: err.message || err.toString() });
  } finally {
    try { if (tempAudio && fs.existsSync(tempAudio)) fs.unlinkSync(tempAudio); } catch (e) {}
  }
};
