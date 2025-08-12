(async () => {
  const { pipeline } = require('@xenova/transformers');

  console.log("📥 Downloading sentiment model...");
  await pipeline("sentiment-analysis", "Xenova/distilbert-base-uncased-finetuned-sst-2-english");

  console.log("📥 Downloading NER model...");
  await pipeline("ner", "Xenova/bert-base-NER");

  console.log("✅ All models downloaded and cached.");
})();
