const fs = require('fs');
const path = require('path');
const ffmpeg = require('fluent-ffmpeg');
const ffmpegPath = require('ffmpeg-static');
const ytdlp = require('yt-dlp-exec');
const axios = require('axios');
const ExcelJS = require('exceljs');

ffmpeg.setFfmpegPath(ffmpegPath);

const HF_TOKEN = process.env.HF_TOKEN;
if(!HF_TOKEN) {
  console.error('HF_TOKEN not set in env!');
}

const HF_WHISPER = 'openai/whisper-large-v3';

// Helper: call Hugging Face inference (binary payload)
async function hfBinaryInference(model, buffer, contentType, accept='application/json') {
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

// Helper: call HF text model (inputs in JSON)
async function hfTextInference(model, inputs) {
  const url = `https://api-inference.huggingface.co/models/${model}`;
  const res = await axios.post(url, { inputs }, {
    headers: { Authorization: `Bearer ${HF_TOKEN}`, 'Content-Type': 'application/json', Accept: 'application/json' },
    timeout: 600000
  });
  return res.data;
}

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

function extractKeyframes(videoPath, outFolder, everySeconds = 3) {
  return new Promise((resolve, reject) => {
    if (!fs.existsSync(outFolder)) fs.mkdirSync(outFolder, { recursive: true });
    // extract one frame every `everySeconds` seconds
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
  console.log(`📥 Downloading from: ${videoUrl}`);

  await ytdlp(videoUrl, {
    output: destPath,
    format: 'mp4',
     proxy: 'http://13.201.84.208:80', // username/password nahi hai
    cookies: path.join(__dirname, '..', 'cookies.txt'),

    // Extra reliability flags
    'socket-timeout': 30,    // seconds
    retries: 5,              // retry on failure
    'retry-sleep': 5,        // wait 5 seconds between retries
    verbose: true            // detailed logs for debugging
  });

  console.log(`✅ Download complete: ${destPath}`);
  return destPath;
}


// Attempt to find hook and CTA within transcript
function findHookAndCTA(transcript) {
  const sentences = transcript
    .split(/[.!?]/)
    .map(s => s.trim())
    .filter(Boolean);

  // Hook heuristic: shortest strong sentence near start (<= 12 words) or first sentence
  let hook = null;
  let hookIndex = -1;
  for (let i = 0; i < Math.min(sentences.length, 6); i++) {
    const s = sentences[i];
    if (s.split(/\s+/).length <= 12) { hook = s; hookIndex = i; break; }
  }
  if (!hook && sentences.length) { hook = sentences[0]; hookIndex = 0; }

  // CTA heuristic: sentence containing verbs like subscribe/buy/click
  const ctaRegex = /(subscribe|buy|download|sign up|click|check out|join|learn more|visit)/i;
  let cta = 'No CTA found';
  let ctaIndex = -1;
  for (let i = sentences.length-1; i >= 0; i--) {
    if (ctaRegex.test(sentences[i])) { cta = sentences[i]; ctaIndex = i; break; }
  }

  return { hook, hookIndex, cta, ctaIndex, sentences };
}

// Map sentence index -> approximate timestamp (naive): proportion by cumulative lengths
function approxTimestampsFromSentences(sentences, durationSeconds) {
  const lengths = sentences.map(s => s.length);
  const total = lengths.reduce((a,b)=>a+b,0) || 1;
  const timestamps = [];
  let accumulated = 0;
  for (let i=0;i<sentences.length;i++){
    const start = Math.floor((accumulated/total) * durationSeconds);
    accumulated += lengths[i];
    const end = Math.floor((accumulated/total) * durationSeconds);
    timestamps.push({ index:i, startSec:start, endSec:end });
  }
  return timestamps;
}

exports.analyzeVideo = async (req, res) => {
  console.log('✅ analyzeVideo called');

  const uploadsDir = path.join(__dirname, '..', 'uploads');
  if (!fs.existsSync(uploadsDir)) fs.mkdirSync(uploadsDir, { recursive: true });

  let localVideoPath = null;
  let tempAudio = null;
  let keyframeDir = null;

  try {
    const videoFile = req.file;
    const videoUrl = req.body.videoUrl || req.body.video_url || null;

    if (!videoFile && !videoUrl) {
      return res.status(400).json({ error: 'Provide uploaded file (field: video) OR videoUrl in body.' });
    }

    // Save video either from upload or by downloading URL
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

    // Read video duration using ffprobe (via ffmpeg)
    const getDuration = () => new Promise((resolve, reject) => {
      ffmpeg.ffprobe(localVideoPath, (err, metadata) => {
        if (err) return reject(err);
        const dur = metadata.format.duration || 0;
        resolve(dur);
      });
    });
    const durationSeconds = Math.round(await getDuration());
    console.log('⏱ Duration (s):', durationSeconds);

    // Extract audio
    tempAudio = localVideoPath.replace(/\.[^/.]+$/, '') + '.wav';
    console.log('🎧 Extracting audio to', tempAudio);
    await extractAudioFromVideo(localVideoPath, tempAudio);
    console.log('✅ Audio extracted');

    // Send audio to Hugging Face Whisper
    const audioBuffer = fs.readFileSync(tempAudio);
    console.log('📝 Sending to Hugging Face Whisper...');
    const whisperRes = await axios.post(
      `https://api-inference.huggingface.co/models/${HF_WHISPER}`,
      audioBuffer,
      {
        headers: {
          Authorization: `Bearer ${HF_TOKEN}`,
          'Content-Type': 'audio/wav',
          Accept: 'application/json'
        },
        timeout: 600000
      }
    );

    // HF Whisper returns object with `text` (and sometimes `segments` with timestamps)
    const whisperData = whisperRes.data;
    const transcript = (whisperData && (whisperData.text || whisperData.transcription || '')) || '';
    const segments = whisperData?.segments || null;
    console.log('📝 Transcript length:', transcript.length);

    // If segments (word timestamps) exist we can map sentences to timestamps; else approximate
    // Basic text postprocessing
    const normalizedTranscript = transcript.replace(/\s+/g,' ').trim();
    const { hook, hookIndex, cta, ctaIndex, sentences } = findHookAndCTA(normalizedTranscript);

    // Map sentences to times
    let sentenceTimestamps = approxTimestampsFromSentences(sentences, durationSeconds);
    if (segments && segments.length > 0) {
      // Convert segments to a sentence mapping if possible (more advanced logic could be added)
      // For now we try to map sentence start by using segment.start for first word of sentence
      // Build a flat list of words from segments
      const words = [];
      for (const seg of segments) {
        if (seg.words) {
          for (const w of seg.words) {
            words.push(w);
          }
        }
      }
      // fallback: leave approx mapping
    }

    // Extract keyframes (every 3 seconds)
    keyframeDir = path.join(uploadsDir, `frames_${Date.now()}`);
    console.log('📸 Extracting keyframes to', keyframeDir);
    const frames = await extractKeyframes(localVideoPath, keyframeDir, 3);
    console.log('✅ Frames extracted:', frames.length);

    // OPTIONAL: analyze frames with HF vision model (SKIPPED by default for speed)
    // Example code placeholder: send frames[i] file to an image model endpoint
    // function analyzeFrameWithHF(filePath) { ... }

    // Generate Excel
    const workbook = new ExcelJS.Workbook();
    const sheet = workbook.addWorksheet('Video Analysis');
    sheet.columns = [
      { header: 'Metric', key: 'metric', width: 30 },
      { header: 'Value', key: 'value', width: 80 }
    ];
    sheet.addRow({ metric: 'Video URL or file', value: videoUrl || path.basename(localVideoPath) });
    sheet.addRow({ metric: 'Duration (s)', value: durationSeconds });
    sheet.addRow({ metric: 'Hook', value: hook || 'Not found' });
    sheet.addRow({ metric: 'Hook sentence index', value: hookIndex });
    sheet.addRow({ metric: 'CTA', value: cta || 'Not found' });
    sheet.addRow({ metric: 'CTA sentence index', value: ctaIndex });
    sheet.addRow({ metric: 'Transcript (truncated)', value: normalizedTranscript.slice(0, 1000) + (normalizedTranscript.length > 1000 ? '...' : '') });
    sheet.addRow({ metric: 'Keyframes extracted (count)', value: frames.length });
    const excelPath = path.join(uploadsDir, `analysis_${Date.now()}.xlsx`);
    await workbook.xlsx.writeFile(excelPath);
    console.log('✅ Excel saved:', excelPath);

    // Build result object with approximate timestamps (based on sentence mapping)
    const sentenceMap = sentenceTimestamps; // [{index, startSec, endSec}]
    let hookTime = null, ctaTime = null;
    if (hookIndex >= 0 && sentenceMap[hookIndex]) hookTime = sentenceMap[hookIndex].startSec;
    if (ctaIndex >= 0 && sentenceMap[ctaIndex]) ctaTime = sentenceMap[ctaIndex].startSec;

    // Return paths (download route) and JSON
    res.json({
      success: true,
      video: videoUrl || path.basename(localVideoPath),
      durationSeconds,
      hook: { text: hook, approxTimeSec: hookTime },
      cta: { text: cta, approxTimeSec: ctaTime },
      transcript: normalizedTranscript,
      frames: frames.map(f => path.relative(path.join(__dirname, '..'), f).replace(/\\/g, '/')),
      excel: path.relative(path.join(__dirname, '..'), excelPath).replace(/\\/g, '/')
    });

  } catch (err) {
    console.error('❌ Analysis Error:', err.response?.data || err.message || err);
    res.status(500).json({ success:false, error: err.response?.data || err.message || err.toString() });
  } finally {
    // Cleanup: remove audio and downloaded video if from URL (but keep excel & frames for download)
    try { if (tempAudio && fs.existsSync(tempAudio)) fs.unlinkSync(tempAudio); } catch(e){}
    // If downloaded from URL, you may want to remove the local video file too. If uploaded by user, keep it (or delete based on policy).
  }
};
