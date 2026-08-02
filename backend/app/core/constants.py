# Analysis stages (in order)
ANALYSIS_STAGES = [
    ("queued",                   "Queued",                      0),
    ("downloading",              "Downloading video",           5),
    ("validating",               "Validating media",            10),
    ("extracting_metadata",      "Extracting metadata",         15),
    ("extracting_audio",         "Extracting audio",            20),
    ("transcribing",             "Transcribing speech",         30),
    ("extracting_frames",        "Extracting keyframes",        38),
    ("analyzing_hooks",          "Detecting hooks",             45),
    ("analyzing_cta",            "Analyzing CTAs",              52),
    ("analyzing_tone",           "Analyzing tone & sentiment",  58),
    ("analyzing_audio",          "Analyzing audio signals",     63),
    ("analyzing_visuals",        "Analyzing visuals",           70),
    ("analyzing_pacing",         "Calculating pacing",          76),
    ("calculating_scores",       "Calculating scores",          82),
    ("generating_recommendations","Generating recommendations", 87),
    ("generating_script",        "Generating improved script",  92),
    ("creating_report",          "Creating report",             96),
    ("completed",                "Completed",                   100),
    ("failed",                   "Failed",                      0),
]

STAGE_MAP = {s[0]: s for s in ANALYSIS_STAGES}

# Allowed video formats
ALLOWED_VIDEO_EXTENSIONS = {".mp4", ".mov", ".avi", ".mkv", ".webm"}
ALLOWED_VIDEO_MIMETYPES = {
    "video/mp4", "video/quicktime", "video/x-msvideo",
    "video/x-matroska", "video/webm",
}

# Allowed URL providers (hostname match)
ALLOWED_URL_HOSTS = {
    "youtube.com", "www.youtube.com", "youtu.be",
    "m.youtube.com", "music.youtube.com",
    "vimeo.com", "www.vimeo.com",
    "twitch.tv", "www.twitch.tv",
    "dailymotion.com", "www.dailymotion.com",
}

# Hook detection
HOOK_TYPES = [
    "question", "curiosity_gap", "bold_claim", "number", "statistic",
    "pain_point", "result_first", "promise", "story", "emotional",
    "authority", "contrarian", "pattern_interrupt", "visual",
]

CTA_TYPES = [
    "subscribe", "follow", "like", "comment", "share",
    "buy", "download", "register", "sign_up", "book",
    "dm", "visit", "try", "link_in_bio", "join", "learn_more",
]

# Score to rating mapping
def score_to_rating(score: float) -> str:
    if score >= 9.0:
        return "Outstanding"
    if score >= 8.0:
        return "Strong"
    if score >= 7.0:
        return "Good"
    if score >= 6.0:
        return "Average"
    if score >= 4.0:
        return "Below Average"
    return "Poor"
