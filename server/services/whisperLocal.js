const { exec } = require('child_process');
const fs = require('fs');
const path = require('path');

exports.transcribeAudio = async (audioPath) => {
  const whisperPath = path.resolve(__dirname, '../../whisper.cpp'); // adjust if needed
  const modelPath = path.join(whisperPath, 'models/ggml-base.en.bin');
  const outputPath = path.join(whisperPath, 'transcribed');

 
  const command = `main.exe -m "${modelPath}" -f "${audioPath}" -otxt -of "${outputPath}"`;

  console.log("🟢 Running whisper command:", command);

  return new Promise((resolve, reject) => {
    exec(command, { cwd: whisperPath }, (error, stdout, stderr) => {
      if (error) {
        console.error('❌ Whisper error:', stderr);
        return reject(error);
      }

      const resultPath = `${outputPath}.txt`;
      try {
        const transcript = fs.readFileSync(resultPath, 'utf-8');
        resolve(transcript);
      } catch (readError) {
        reject(readError);
      }
    });
  });
};
