const { exec } = require("child_process");
const fs = require("fs");
const path = require("path");

exports.transcribeAudio = async (audioPath) => {
  // Resolve all paths
  const whisperPath = path.resolve(__dirname, "../../whisper.cpp");
  const exePath = path.join(whisperPath, "main.exe"); // Full path to main.exe
  const modelPath = path.join(whisperPath, "models", "ggml-base.en.bin");
  const outputPath = path.join(whisperPath, "transcribed");

  // Validate files
  if (!fs.existsSync(exePath)) throw new Error(`Whisper binary not found: ${exePath}`);
  if (!fs.existsSync(modelPath)) throw new Error(`Model file not found: ${modelPath}`);
  if (!fs.existsSync(audioPath)) throw new Error(`Audio file not found: ${audioPath}`);

  // Quote paths to handle spaces
  const command = `"${exePath}" -m "${modelPath}" -f "${audioPath}" -otxt -of "${outputPath}"`;

  console.log("🟢 Running whisper command:", command);

  return new Promise((resolve, reject) => {
    exec(command, { cwd: whisperPath }, (error, stdout, stderr) => {
      if (error) {
        console.error("❌ Whisper error:", stderr || error.message);
        return reject(error);
      }

      const resultPath = `${outputPath}.txt`;

      if (!fs.existsSync(resultPath)) {
        return reject(new Error(`Transcript file not found: ${resultPath}`));
      }

      try {
        const transcript = fs.readFileSync(resultPath, "utf-8");
        console.log("✅ Transcription complete");
        resolve(transcript);
      } catch (readError) {
        reject(readError);
      }
    });
  });
};

