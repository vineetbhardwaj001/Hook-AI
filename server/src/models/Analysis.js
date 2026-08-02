const mongoose = require('mongoose');

const analysisSchema = new mongoose.Schema({
  userId: { type: mongoose.Schema.Types.ObjectId, ref: 'User', default: null },
  videoSource: { type: String, required: true },   // filename or YouTube URL
  videoType: { type: String, enum: ['upload', 'youtube', 'link'], default: 'upload' },
  duration: { type: String, default: '0:00' },
  fileSize: { type: Number, default: 0 },          // bytes

  // Scores (0-10)
  overallScore:       { type: Number, default: 0 },
  hookStrength:       { type: Number, default: 0 },
  ctaEffectiveness:   { type: Number, default: 0 },
  engagementPotential:{ type: Number, default: 0 },
  speechQuality:      { type: Number, default: 0 },

  // Converted to /100
  hookStrength100:       { type: Number, default: 0 },
  ctaEffectiveness100:   { type: Number, default: 0 },
  engagementPotential100:{ type: Number, default: 0 },
  retention100:          { type: Number, default: 0 },
  overallScore100:       { type: Number, default: 0 },

  // Hook & CTA
  hookText:    { type: String, default: '' },
  hookTiming:  { type: String, default: '0:00' },
  ctaText:     { type: String, default: '' },
  ctaTiming:   { type: String, default: '0:00' },
  ctaType:     { type: String, default: '' },

  // Sentiment
  sentimentLabel:   { type: String, default: 'Neutral' },
  sentimentScore:   { type: Number, default: 0.5 },
  primaryEmotion:   { type: String, default: 'Neutral' },
  tones:            [{ type: String }],

  // Transcript
  wordCount:  { type: Number, default: 0 },
  wpm:        { type: String, default: '0 WPM' },
  transcript: { type: String, default: '' },

  // Topics
  topics:   [{ type: String }],
  entities: [{ type: String }],

  // AI
  aiSuggestions: [{ title: String, description: String, category: String }],
  linkAnalysis: { type: String, default: '' },

  status: { type: String, enum: ['completed', 'failed'], default: 'completed' },
}, { timestamps: true });

module.exports = mongoose.model('Analysis', analysisSchema);
