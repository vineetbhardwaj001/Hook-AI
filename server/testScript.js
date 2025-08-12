const { simpleGenScript } = require('./services/simpleNLP');

(async () => {
  const script = await simpleGenScript(
    'sales',
    'funny',
    'AI fitness app\nBenefits: tracks calories, gives voice feedback\nAudience: gym lovers\nPlatform: Instagram Reels'
  );
  console.log("📝 Script generated:\n", script);
})();  