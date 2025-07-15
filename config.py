# config.py

import os

# --- API Keys ---
# WARNING: Embedding API keys directly in code is NOT recommended for production environments.
# For better security, always use environment variables or a more secure secrets management solution.

# --- NEW: Hugging Face Configuration ---
# The script will use the HF_TOKEN secret from your GitHub repository settings or a local .env file.
HUGGING_FACE_TOKEN = os.getenv("HF_TOKEN", "YOUR_HUGGING_FACE_TOKEN")
INFERENCE_API_ENDPOINTS = [
    "https://api-inference.huggingface.co/models/black-forest-labs/FLUX.1-schnell",
    "https://api-inference.huggingface.co/models/stabilityai/stable-diffusion-3-medium-diffusers",
    "https://api-inference.huggingface.co/models/stabilityai/stable-diffusion-xl-base-1.0",
    "https://api-inference.huggingface.co/models/runwayml/stable-diffusion-v1-5",
    "https://api-inference.huggingface.co/models/CompVis/stable-diffusion-v1-4"
]

# --- API Keys (from environment variables) ---
OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")
OPENROUTER_MODEL = "deepseek/deepseek-chat-v3-0324:free"
OPENROUTER_SITE_URL = "https://insightpulse.com"
OPENROUTER_SITE_NAME = "Insight Pulse"

OPENROUTER_MISTRAL_API_KEY = os.getenv("OPENROUTER_MISTRAL_API_KEY")
OPENROUTER_MISTRAL_MODEL = "mistralai/mistral-small-3.2-24b-instruct:free"

OPENROUTER_DEEPSEEK_R1_API_KEY = os.getenv("OPENROUTER_DEEPSEEK_R1_API_KEY")
OPENROUTER_DEEPSEEK_R1_MODEL = "deepseek/deepseek-r1-0528:free"

PEXELS_API_KEY = os.getenv("PEXELS_API_KEY")
PEXELS_API_URL = "https://api.pexels.com/v1"

UNSPLASH_ACCESS_KEY = os.getenv("UNSPLASH_ACCESS_KEY")
UNSPLASH_API_URL = "https://api.unsplash.com"

OPENVERSE_API_URL = "https://api.openverse.engineering/v1/images/"

PIXABAY_API_KEY = os.getenv("PIXABAY_API_KEY")
PIXABAY_API_URL = "https://pixabay.com/api/"

CLOUDINARY_CLOUD_NAME = os.getenv("CLOUDINARY_CLOUD_NAME")
CLOUDINARY_API_KEY = os.getenv("CLOUDINARY_API_KEY")
CLOUDINARY_API_SECRET = os.getenv("CLOUDINARY_API_SECRET")

FB_PAGE_ACCESS_TOKEN = os.getenv("FB_PAGE_ACCESS_TOKEN")
INSTAGRAM_BUSINESS_ACCOUNT_ID = os.getenv("INSTAGRAM_BUSINESS_ACCOUNT_ID")

# --- Output Directories and Files ---
IMAGE_OUTPUT_DIR = "output/images"
JSON_OUTPUT_DIR = "output/json"
EXCEL_OUTPUT_DIR = "output/excel"

ALL_POSTS_JSON_FILE = f"{JSON_OUTPUT_DIR}/all_posts.json"
ALL_POSTS_EXCEL_FILE = f"{EXCEL_OUTPUT_DIR}/all_posts.xlsx"
STYLE_RECOMMENDATIONS_FILE = f"{JSON_OUTPUT_DIR}/style_recommendations.json"
INSTAGRAM_ANALYSIS_FILE = f"{JSON_OUTPUT_DIR}/instagram_analysis.json"
EXTERNAL_INSTAGRAM_ANALYSIS_FILE = f"{JSON_OUTPUT_DIR}/external_instagram_analysis.json"


# --- Analysis Configuration ---
WEEKLY_ANALYSIS_INTERVAL_DAYS = 7 # For internal content analysis
INSTAGRAM_ANALYSIS_INTERVAL_DAYS = 3 # For internal Instagram post performance analysis
EXTERNAL_INSTAGRAM_ANALYSIS_INTERVAL_DAYS = 7 # For conceptual external Instagram analysis

# --- Canvas Dimensions (Instagram Square Post) ---
CANVAS_WIDTH = 1080
CANVAS_HEIGHT = 1350 # 4:5 aspect ratio, common for Instagram portrait posts

# --- Font Paths (ensure these paths are correct relative to your script) ---
FONT_PATH_EXTRABOLD = "fonts/Montserrat-ExtraBold.ttf"
FONT_PATH_BOLD = "fonts/Montserrat-Bold.ttf"
FONT_PATH_MEDIUM = "fonts/Montserrat-Medium.ttf"
FONT_PATH_REGULAR = "fonts/Montserrat-Regular.ttf"
FONT_PATH_LIGHT = "fonts/Montserrat-Light.ttf"

FONT_PATH_ALFA_SLAB_ONE = "fonts/AlfaSlabOne-Regular.ttf"
FONT_PATH_TAPESTRY = "fonts/Tapestry-Regular.ttf"


# --- Colors (RGBA format) ---
# Existing News Post Colors
INSTA_COLOR_DARK_BLUE = (17, 45, 78, 255) # #112D4E
INSTA_COLOR_MEDIUM_BLUE = (63, 114, 175, 255) # #3F72AF
INSTA_COLOR_LIGHT_BLUE = (219, 226, 239, 255) # #DBE2EF
INSTA_COLOR_VERY_LIGHT_GRAY = (249, 247, 247, 255) # #F9F7F7

COLOR_GRADIENT_TOP_LEFT = INSTA_COLOR_VERY_LIGHT_GRAY
COLOR_GRADIENT_BOTTOM_RIGHT = INSTA_COLOR_LIGHT_BLUE

COLOR_HEADLINE_TEXT = INSTA_COLOR_DARK_BLUE
COLOR_SUMMARY_TEXT = INSTA_COLOR_DARK_BLUE
COLOR_TOP_LEFT_TEXT = INSTA_COLOR_MEDIUM_BLUE
COLOR_TIMESTAMP_TEXT = INSTA_COLOR_DARK_BLUE
COLOR_SOURCE_BOX_FILL = INSTA_COLOR_DARK_BLUE # Not used for display
COLOR_SOURCE_TEXT = INSTA_COLOR_VERY_LIGHT_GRAY # Not used for display
COLOR_DIVIDER_LINE = INSTA_COLOR_MEDIUM_BLUE

# NEW: Motivational quote specific colors
QUOTE_COLOR_ACCENT = (178, 69, 110, 255) # #B2456E
QUOTE_COLOR_BACKGROUND_LIGHT = (251, 234, 231, 255) # #FBEAE7
QUOTE_COLOR_TEXT_DARK =  (85, 38, 25, 255) # #552619

# NEW: Border color and thickness for all posts
BORDER_COLOR = INSTA_COLOR_MEDIUM_BLUE
BORDER_THICKNESS = 5


# --- Font Sizes ---
# News Post Font Sizes
FONT_SIZE_TOP_LEFT_TEXT = 30 # Reduced for balance
FONT_SIZE_TIMESTAMP = 35
FONT_SIZE_HEADLINE = 60
FONT_SIZE_SUMMARY = 42
FONT_SIZE_SOURCE = 35 # Not used for display

# Motivational Quote Post Font Sizes
FONT_SIZE_QUOTE = 60 # Large and prominent for quotes
FONT_SIZE_QUOTE_AUTHOR = 30 # Slightly smaller for author


# --- Padding and Margins ---
LEFT_PADDING = 20
RIGHT_PADDING = 20
TOP_PADDING = 10
BOTTOM_PADDING = 10

TOP_LEFT_TEXT_POS_X = LEFT_PADDING
TOP_LEFT_TEXT_POS_Y = TOP_PADDING

TIMESTAMP_POS_X_RIGHT_ALIGN = CANVAS_WIDTH - RIGHT_PADDING
TIMESTAMP_POS_Y = TOP_PADDING

IMAGE_DISPLAY_WIDTH = CANVAS_WIDTH - (LEFT_PADDING + RIGHT_PADDING)
IMAGE_DISPLAY_HEIGHT = int(CANVAS_HEIGHT * 0.40)
IMAGE_TOP_MARGIN_FROM_TOP_ELEMENTS = 35
IMAGE_ROUND_RADIUS = 28

TITLE_TOP_MARGIN_FROM_IMAGE = 30
TITLE_MAX_WORDS = 5
TITLE_LINE_SPACING = 10

SUMMARY_TOP_MARGIN_FROM_TITLE = 55
SUMMARY_MIN_WORDS = 50
SUMMARY_MAX_WORDS = 70
SUMMARY_LINE_SPACING = 12
SUMMARY_MAX_LINES = 6
SUMMARY_REGENERATE_ATTEMPTS = 4

# --- Logo ---
LOGO_PATH = "assets/insight_pulse_logo.png"
LOGO_WIDTH = 580
LOGO_HEIGHT = 230
LOGO_BOTTOM_MARGIN = 20 # Margin from bottom of canvas for news post logo placement

# Motivational Quote Post Logo Specifics (Can be different if needed)
QUOTE_LOGO_WIDTH = 600 # Smaller logo for quote posts
QUOTE_LOGO_HEIGHT = 200
QUOTE_LOGO_BOTTOM_MARGIN = 3 # Margin from bottom for quote post logo


# --- Divider Line (News Post) ---
DIVIDER_Y_OFFSET_FROM_SUMMARY = 50
DIVIDER_LINE_THICKNESS = 6

# --- Quote Section (Constants) --- # RE-ADDED THESE MISSING CONSTANTS
QUOTE_BOX_HEIGHT = 180 # Fixed height for the quote box
QUOTE_BOX_MARGIN_FROM_DIVIDER = 20 # Margin between divider and quote box
QUOTE_TEXT_PADDING_X = 20
QUOTE_TEXT_PADDING_Y = 20
QUOTE_BOX_RADIUS = 20


# --- Source Box (Removed as requested, but keeping related variables here for clarity if ever needed) ---
# SOURCE_RECT_PADDING_X = 35
# SOURCE_RECT_PADDING_Y = 20
# SOURCE_RECT_RADIUS = 25
# SOURCE_POS_X_RIGHT_ALIGN = CANVAS_WIDTH - RIGHT_PADDING


# --- Workflow State Management ---
# Added 'motivational_quote_post' to the cycle
CONTENT_TYPE_CYCLE = [
    'startup_news',
    'business_news',
     'motivational_quote_post', # NEW: Dedicated post type for quotes
    'financial_news',
    'entrepreneurial_news',
    'motivational_quote_post', # NEW: Dedicated post type for quotes
    'startup_news',
    'business_news',
    'financial_news',
    'entrepreneurial_news',
]
