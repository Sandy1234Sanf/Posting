# main.py

import requests
import json
import os
import pandas as pd
from datetime import datetime, timedelta, UTC
from PIL import Image, ImageDraw, ImageFont, ImageOps, ImageFilter
import textwrap
import io
import random
import feedparser
import ssl
import re
import sys
from openai import OpenAI
import cloudinary
import cloudinary.uploader

# Fix for some SSL certificate issues with feedparser on some systems
if hasattr(ssl, '_create_unverified_context'):
    ssl._create_default_https_context = ssl._create_unverified_context


# Import configuration and state manager
from Test import (
    OPENROUTER_API_KEY, OPENROUTER_MODEL, OPENROUTER_SITE_URL, OPENROUTER_SITE_NAME,
    OPENROUTER_MISTRAL_API_KEY, OPENROUTER_MISTRAL_MODEL,
    OPENROUTER_DEEPSEEK_R1_API_KEY, OPENROUTER_DEEPSEEK_R1_MODEL,DIVIDER_LINE_THICKNESS,DIVIDER_Y_OFFSET_FROM_SUMMARY, # Corrected typo here
    PEXELS_API_KEY, PEXELS_API_URL,
    UNSPLASH_ACCESS_KEY, UNSPLASH_API_URL,
    OPENVERSE_API_URL,
    PIXABAY_API_KEY, PIXABAY_API_URL,
    CLOUDINARY_CLOUD_NAME, CLOUDINARY_API_KEY, CLOUDINARY_API_SECRET,
    FB_PAGE_ACCESS_TOKEN, INSTAGRAM_BUSINESS_ACCOUNT_ID,
    IMAGE_OUTPUT_DIR, JSON_OUTPUT_DIR, EXCEL_OUTPUT_DIR,
    ALL_POSTS_JSON_FILE, ALL_POSTS_EXCEL_FILE, STYLE_RECOMMENDATIONS_FILE,
    INSTAGRAM_ANALYSIS_FILE, EXTERNAL_INSTAGRAM_ANALYSIS_FILE,
    WEEKLY_ANALYSIS_INTERVAL_DAYS, INSTAGRAM_ANALYSIS_INTERVAL_DAYS, EXTERNAL_INSTAGRAM_ANALYSIS_INTERVAL_DAYS,
    CANVAS_WIDTH, CANVAS_HEIGHT,
    FONT_PATH_EXTRABOLD, FONT_PATH_BOLD, FONT_PATH_MEDIUM, FONT_PATH_REGULAR, FONT_PATH_LIGHT,
    FONT_PATH_ALFA_SLAB_ONE, FONT_PATH_TAPESTRY,
    COLOR_GRADIENT_TOP_LEFT, COLOR_GRADIENT_BOTTOM_RIGHT,
    COLOR_HEADLINE_TEXT, COLOR_SUMMARY_TEXT, COLOR_TOP_LEFT_TEXT, COLOR_TIMESTAMP_TEXT,
    COLOR_SOURCE_BOX_FILL, COLOR_SOURCE_TEXT,
    COLOR_DIVIDER_LINE,
    BORDER_COLOR, BORDER_THICKNESS,
    QUOTE_COLOR_ACCENT, QUOTE_COLOR_BACKGROUND_LIGHT, QUOTE_COLOR_TEXT_DARK,
    FONT_SIZE_TOP_LEFT_TEXT, FONT_SIZE_TIMESTAMP, FONT_SIZE_HEADLINE, FONT_SIZE_SUMMARY,
    FONT_SIZE_QUOTE, FONT_SIZE_QUOTE_AUTHOR,
    LEFT_PADDING, RIGHT_PADDING, TOP_PADDING, BOTTOM_PADDING,
    TOP_LEFT_TEXT_POS_X, TOP_LEFT_TEXT_POS_Y,
    TIMESTAMP_POS_X_RIGHT_ALIGN, TIMESTAMP_POS_Y,
    IMAGE_DISPLAY_WIDTH, IMAGE_DISPLAY_HEIGHT, IMAGE_TOP_MARGIN_FROM_TOP_ELEMENTS, IMAGE_ROUND_RADIUS,
    TITLE_TOP_MARGIN_FROM_IMAGE, TITLE_MAX_WORDS, TITLE_LINE_SPACING,
    SUMMARY_TOP_MARGIN_FROM_TITLE, SUMMARY_MIN_WORDS, SUMMARY_MAX_WORDS, SUMMARY_LINE_SPACING, SUMMARY_MAX_LINES,
    LOGO_PATH, LOGO_WIDTH, LOGO_HEIGHT, LOGO_BOTTOM_MARGIN,
    QUOTE_LOGO_WIDTH, QUOTE_LOGO_HEIGHT, QUOTE_LOGO_BOTTOM_MARGIN,
    QUOTE_BOX_HEIGHT, QUOTE_BOX_MARGIN_FROM_DIVIDER, QUOTE_TEXT_PADDING_X, QUOTE_TEXT_PADDING_Y, QUOTE_BOX_RADIUS, # Re-added for import
    CONTENT_TYPE_CYCLE
)
from state_manager import WorkflowStateManager

# --- Utility Functions ---

def load_font(font_path, size):
    """Loads a font with error handling."""
    try:
        return ImageFont.truetype(font_path, size)
    except IOError:
        print(f"Error: Font file not found at {font_path}. Please ensure the font file exists in the 'fonts' folder.")
        if "AlfaSlabOne" in font_path:
            return ImageFont.truetype(FONT_PATH_BOLD, size)
        elif "Tapestry" in font_path:
            return ImageFont.truetype(FONT_PATH_REGULAR, size)
        return ImageFont.load_default()
    except Exception as e:
        print(f"Error loading font {font_path}: {e}. Falling back to default.")
        return ImageFont.load_default()

def wrap_text_by_word_count(text, font, max_width_pixels, max_words=None):
    """
    Wraps text to fit within a given pixel width and optionally truncates by word count,
    returning a list of lines.
    Uses a dummy ImageDraw.Draw object for accurate textbbox calculation.
    """
    if not text:
        return [""]

    words = text.split(' ')

    original_text_length = len(words)
    if max_words is not None and original_text_length > max_words:
        words = words[:max_words]
        text_to_wrap = ' '.join(words) + "..."
    else:
        text_to_wrap = ' '.join(words)

    lines = []
    current_line_words = []

    dummy_img = Image.new('RGB', (1,1))
    dummy_draw = ImageDraw.Draw(dummy_img)

    for word in text_to_wrap.split(' '):
        test_line = ' '.join(current_line_words + [word])

        text_bbox = dummy_draw.textbbox((0,0), test_line, font=font)
        text_width = text_bbox[2] - text_bbox[0]

        if text_width <= max_width_pixels:
            current_line_words.append(word)
        else:
            if current_line_words:
                lines.append(' '.join(current_line_words))
            current_line_words = [word]

    if current_line_words:
        lines.append(' '.join(current_line_words))

    return lines

# --- Background Generator ---
class BackgroundGenerator:
    """Generates the gradient background for the post."""
    def generate_gradient_background(self, width, height, color1, color2):
        """Creates a diagonal gradient image."""
        img = Image.new('RGBA', (width, height), color1)
        draw = ImageDraw.Draw(img)

        for y in range(height):
            r1, g1, b1, a1 = color1
            r2, g2, b2, a2 = color2

            ratio_y = y / height

            r = int(r1 + (r2 - r1) * ratio_y)
            g = int(g1 + (g2 - g1) * ratio_y)
            b = int(b1 + (b2 - b1) * ratio_y)
            a = int(a1 + (a2 - a1) * ratio_y)

            draw.line([(0, y), (width, y)], fill=(r, g, b, a))

        return img


# --- API Callers ---

class NewsFetcher:
    """Fetches news from various RSS feeds."""

    def _fetch_from_rss(self, rss_url, article_count=1, time_window_hours=72):
        """Fetches and parses articles from an RSS feed, filtering by recency."""
        try:
            feed = feedparser.parse(rss_url)
            if feed.bozo:
                print(f"Warning: RSS feed parsing issues for {rss_url}: {feed.bozo_exception}")

            recent_articles = []
            time_threshold = datetime.now(UTC) - timedelta(hours=time_window_hours)

            for entry in feed.entries:
                # Ensure published_dt_candidate is always assigned a datetime object
                published_dt_candidate = None # Use a candidate variable name
                if hasattr(entry, 'published_parsed') and entry.published_parsed:
                    published_dt_candidate = datetime(*entry.published_parsed[:6], tzinfo=UTC)
                elif hasattr(entry, 'updated_parsed') and entry.updated_parsed:
                    published_dt_candidate = datetime(*entry.updated_parsed[:6], tzinfo=UTC)
                
                # If after checking, it's still None, assign current time as fallback
                if published_dt_candidate is None: # Explicitly check for None
                    published_dt_candidate = datetime.now(UTC) # Fallback to now if no publish date

                if published_dt_candidate > time_threshold:
                    raw_description = entry.summary if hasattr(entry, 'summary') and entry.summary else (entry.title if hasattr(entry, 'title') else 'No Description')
                    clean_description = re.sub(r'<[^>]+>', '', raw_description).strip()
                    clean_description = re.sub(r'\s+', ' ', clean_description).strip()

                    recent_articles.append({
                        'title': entry.title if hasattr(entry, 'title') and entry.title else 'No Title',
                        'description': clean_description,
                        'url': entry.link if hasattr(entry, 'link') else rss_url,
                        'source': feed.feed.title if hasattr(feed.feed, 'title') and feed.feed.title else 'Unknown RSS',
                        # FIX: Use published_dt_candidate here
                        'publishedAt': published_dt_candidate.isoformat()
                    })
                    if len(recent_articles) >= article_count:
                        break

            return recent_articles

        except Exception as e:
            print(f"Error fetching from RSS feed {rss_url}: {e}")
            return []


    def get_single_content_item(self, content_type: str):
        """
        Fetches a single content item based on the specified type, using only RSS feeds.
        Returns None if no recent, relevant content can be found.
        """
        # No news fetching for motivational_quote_post type
        if content_type == 'motivational_quote_post':
            return None # Indicate no news item for this type

        startup_news_sources = [
            {'type': 'rss', 'url': 'https://techcrunch.com/category/startups/feed/', 'name': 'TechCrunch Startups'},
            {'type': 'rss', 'url': 'https://feeds.feedburner.com/Forbes/Innovation', 'name': 'Forbes Innovation'},
            {'type': 'rss', 'url': 'https://www.inc.com/feed.xml', 'name': 'Inc. Magazine'},
            {'type': 'rss', 'url': 'https://www.entrepreneur.com/latest.rss', 'name': 'Entrepreneur Magazine (Startup)'},
            {'type': 'rss', 'url': 'https://www.wired.com/feed/category/business/latest/rss', 'name': 'Wired Business (Startup)'},
            {'type': 'rss', 'url': 'https://sifted.eu/feed/', 'name': 'Sifted EU Startups'},
            {'type': 'rss', 'url': 'https://www.startupgrind.com/blog/rss/', 'name': 'Startup Grind Blog'},
            {'type': 'rss', 'url': 'https://venturebeat.com/category/startup/feed/', 'name': 'VentureBeat Startup'},
        ]

        business_news_sources = [
            {'type': 'rss', 'url': 'https://www.reuters.com/business/rss', 'name': 'Reuters Business News'},
            {'type': 'rss', 'url': 'https://www.wsj.com/xml/rss/SHELF/Public.xml', 'name': 'Wall Street Journal Business'},
            {'type': 'rss', 'url': 'https://www.cnbc.com/id/10001147/device/rss/rss.html', 'name': 'CNBC Business News'},
            {'type': 'rss', 'url': 'https://feeds.bloomberg.com/businessweek/rss.xml', 'name': 'Bloomberg Businessweek'},
            {'type': 'rss', 'url': 'https://hbr.org/rss/articles', 'name': 'Harvard Business Review'},
            {'type': 'rss', 'url': 'https://www.ft.com/rss/companies', 'name': 'Financial Times Companies'},
            {'type': 'rss', 'url': 'https://www.businessinsider.com/feed', 'name': 'Business Insider'},
            {'type': 'rss', 'url': 'https://www.theguardian.com/business/rss', 'name': 'The Guardian Business'},
        ]

        financial_news_sources = [
            {'type': 'rss', 'url': 'https://www.reuters.com/markets/rss', 'name': 'Reuters Markets News'},
            {'type': 'rss', 'url': 'https://feeds.a.dj.com/rss/RssCommon.xml', 'name': 'Dow Jones News (Financial)'},
            {'type': 'rss', 'url': 'https://www.ft.com/rss/markets', 'name': 'Financial Times Markets'},
            {'type': 'rss', 'url': 'https://investing.com/rss/news_top.rss', 'name': 'Investing.com News'},
            {'type': 'rss', 'url': 'https://www.bloomberg.com/feeds/markets.rss', 'name': 'Bloomberg Markets'},
            {'type': 'rss', 'url': 'https://seekingalpha.com/feed.xml', 'name': 'Seeking Alpha'},
            {'type': 'rss', 'url': 'https://www.marketwatch.com/rss/marketwatch/topstories.xml', 'name': 'MarketWatch Top Stories'},
            {'type': 'rss', 'url': 'https://www.investopedia.com/feed.rss', 'name': 'Investopedia'},
        ]

        entrepreneurial_news_sources = [
            {'type': 'rss', 'url': 'https://www.entrepreneur.com/latest.rss', 'name': 'Entrepreneur Magazine'},
            {'type': 'rss', 'url': 'https://www.forbes.com/entrepreneurs/feed/', 'name': 'Forbes Entrepreneurs'},
            {'type': 'rss', 'url': 'https://www.inc.com/feed.xml', 'name': 'Inc. Magazine (Entrepreneurial)'},
            {'type': 'rss', 'url': 'https://www.businessinsider.com/feed?startup=true', 'name': 'Business Insider Startups (Entrepreneur)'},
            {'type': 'rss', 'url': 'https://www.fastcompany.com/feed', 'name': 'Fast Company (Entrepreneurship)'},
            {'type': 'rss', 'url': 'https://www.startups.co.uk/feed/', 'name': 'Startups.co.uk'},
            {'type': 'rss', 'url': 'https://foundr.com/feed/', 'name': 'Foundr Magazine'},
            {'type': 'rss', 'url': 'https://www.ycombinator.com/blog/rss', 'name': 'Y Combinator Blog'},
        ]

        content_item = None
        articles = []
        selected_sources = []

        if content_type == 'startup_news':
            selected_sources = startup_news_sources
        elif content_type == 'business_news':
            selected_sources = business_news_sources
        elif content_type == 'financial_news':
            selected_sources = financial_news_sources
        elif content_type == 'entrepreneurial_news':
            selected_sources = entrepreneurial_news_sources
        else:
            print(f"Unknown content type requested: {content_type}. Please select from valid types.")
            return None

        random.shuffle(selected_sources)
        for source_info in selected_sources:
            print(f"Fetching {content_type.replace('_', ' ').title()} from: {source_info['name']} ({source_info['type']})...")
            articles = self._fetch_from_rss(source_info['url'], article_count=1)
            if articles:
                break

        if articles:
            article = articles[0]
            source_name = article.get('source', f'Unknown {content_type.replace("_", " ").title()} Source')

            content_item = {
                'type': content_type,
                'title': article.get('title', 'No Title'),
                'description': article.get('description', article.get('title', 'No Description')),
                'url': article.get('url', ''),
                'source': source_name,
                'publishedAt': article.get('publishedAt', datetime.now(UTC).isoformat()) # This is correct now, as _fetch_from_rss sets 'publishedAt'
            }
        else:
            print(f"No recent RSS articles found for {content_type.replace('_', ' ').title()}.")
            return None

        return content_item


class TextProcessor:
    """Summarizes and enhances text using OpenRouter AI (DeepSeek model) with storytelling."""

    def __init__(self):
        self.api_key = OPENROUTER_API_KEY
        self.model = OPENROUTER_MODEL
        self.site_url = OPENROUTER_SITE_URL
        self.site_name = OPENROUTER_SITE_NAME
        self.client = OpenAI(
            base_url="https://openrouter.ai/api/v1",
            api_key=self.api_key,
        )

        self.storytelling_methods = [
            "The Burning Question: Start with a captivating, unsolved question directly related to the news. (e.g., 'What if one decision could change your entire financial future?')",
            "The Unexpected Twist: Begin by setting up a common expectation, then introduce a surprising, contradictory element from the news. (e.g., 'They said it couldn't be done, but this startup just proved them wrong.')",
            "The Ripple Effect: Focus on the immediate and cascading consequences of an event, building curiosity about its broader impact. (e.g., 'A single policy change is sending shockwaves through the market... here's what it means for YOU.')",
            "The Human Element: Center the narrative around the personal journey, struggle, or triumph of an individual or small group within the news. (e.g., 'From garage to global empire: Meet the entrepreneur who defied all odds.')",
            "The Hypothetical Future: Explore a 'what-if' scenario, painting a vivid picture of potential outcomes based on current trends or news. (e.g., 'Imagine a world where your investments grow even while you sleep. This new strategy might make it real.')",
            "The Myth Buster: Challenge a widely held belief or assumption by presenting new evidence or a counter-narrative from the news. (e.g., 'Forget everything you know about traditional business models. This disruptor is rewriting the rules.')",
            "The Origin Story: Delve into the hidden beginnings or foundational moments of a significant development. (e.g., 'Before it became a household name, this fintech giant started with a single, audacious idea.')",
            "The Unveiling Mystery: Create a sense of suspense by hinting at a significant discovery or reveal, drawing the reader towards the resolution. (e.g., 'The secret ingredient to this company's meteoric rise is finally being exposed.')"
        ]


    def _call_ai_api(self, messages):
        """Helper to call the OpenRouter API using the OpenAI client. Returns (short_title, summary, chosen_method, success_flag)."""
        if self.api_key == "sk-or-v1-YOUR_DEEPSEEK_CHAT_API_KEY_HERE":
            print("OPENROUTER_API_KEY for Deepseek Chat is a placeholder. Skipping AI text processing.")
            return "AI Key Error", "Please set your OpenRouter API key in config.py.", "None", False

        try:
            completion = self.client.chat.completions.create(
                extra_headers={
                    "HTTP-Referer": self.site_url,
                    "X-Title": self.site_name,
                },
                model=self.model,
                messages=messages,
                temperature=0.8,
                max_tokens=600,
                response_format={"type": "json_object"}
            )

            if completion.choices and completion.choices[0].message and completion.choices[0].message.content:
                ai_content_str = completion.choices[0].message.content
                try:
                    parsed_data = json.loads(ai_content_str)
                    short_title = parsed_data.get('short_title', "Untitled Story")
                    summary = parsed_data.get('summary_text', "No captivating story available.")
                    chosen_method = parsed_data.get('storytelling_method', "Unknown")

                    title_words = short_title.split()
                    short_title = ' '.join(title_words[:TITLE_MAX_WORDS]) if len(title_words) > TITLE_MAX_WORDS else short_title

                    summary_words = summary.split()
                    if len(summary_words) > SUMMARY_MAX_WORDS:
                        summary = ' '.join(summary_words[:SUMMARY_MAX_WORDS]) + "..."

                    return short_title, summary, chosen_method, True
                except json.JSONDecodeError:
                    print(f"Warning: OpenRouter (Deepseek Chat) did not return valid JSON. Raw response: {ai_content_str[:200]}...")
                    return "AI Storytelling Error", "AI summary generation failed. Check API response.", "JSON Error", False

            print(f"OpenRouter (Deepseek Chat) response missing expected content: {completion}")
            return "AI Response Error", "AI response structure invalid.", "Empty Response", False

        except Exception as e:
            print(f"Error calling OpenRouter (Deepseek Chat) API: {e}")
            return "API Error", f"AI API request failed: {e}", "API Call Failed", False


    def process_text(self, title, description, post_type, style_recommendations=""):
        """Generates concise title and summary for a given post using OpenRouter AI (Deepseek),
        focusing on storytelling elements. Returns (short_title, summary, chosen_method, success_flag).
        """
        # Text processing is only for news content
        if post_type == 'motivational_quote_post':
            return None, None, "N/A", False # No text processing needed for quotes

        method_list_str = "\n".join([f"- {m}" for m in self.storytelling_methods])

        system_message_content = f"""
        You are a highly creative and engaging content summarizer for social media posts, specializing in Startup, Business, Financial, and Entrepreneurial news.
        Your primary goal is to transform standard news into compelling, curiosity-driven narratives,
        using one of the following storytelling methods for the headline and summary.
        You MUST choose ONE of these storytelling methods and apply it consistently to both the headline and the summary.

        Available Storytelling Methods to Experiment With:
        {method_list_str}

        The headline should be impactful and immediately grab attention, posing a question, setting up a "what if," building suspense, highlighting a paradox, or hinting at a future implication.
        The summary must follow up on the headline's hook and deliver the core information.

        CRUCIAL: The content (summary_text) MUST be very useful and complete, providing sufficient information for the reader,
        UNLESS the chosen storytelling method explicitly implies an open-ended narrative (e.g., 'The Burning Question' or 'The Hypothetical Future' might end with a thoughtful question, but still provide foundational context).
        Adhere strictly to the word and line count constraints. The output MUST always be a valid JSON object.
        Consider the following style recommendations from past performance analysis when crafting the content: {style_recommendations}
        """

        user_message_content = f"""
        Generate a compelling headline and a detailed summary for the following content, using one of the specified storytelling methods.

        Constraints:
        1. The headline (short_title) MUST be concise, aiming for {TITLE_MAX_WORDS} words or fewer, and embody the chosen storytelling method.
        2. The summary (summary_text) MUST be between {SUMMARY_MIN_WORDS} and {SUMMARY_MAX_WORDS} words.
        3. The summary should flow naturally from the headline's hook and provide enough context, being useful and complete, unless the storytelling method inherently leaves it open.
        4. The summary should aim for approximately {SUMMARY_MAX_LINES} lines when formatted for display on a social media image (assuming a width of {CANVAS_WIDTH - (LEFT_PADDING + RIGHT_PADDING)} pixels with font size {FONT_SIZE_SUMMARY}).

        Content Type: {post_type.replace('_', ' ').title()}
        Original Title: {title}
        Original Description: {description}

        Return ONLY the JSON object with three keys: "short_title", "summary_text", and "storytelling_method".
        Example Output:
        {{
          "short_title": "The Silent Revolution Reshaping Finance?",
          "summary_text": "A new decentralized finance (DeFi) protocol is quietly gaining traction, promising to disrupt traditional banking with its transparent and automated lending systems. This innovative approach could bypass intermediaries entirely, offering unprecedented access to capital for small businesses and individuals. Is this the future, or just another fleeting trend? Only time will tell.",
          "storytelling_method": "The Burning Question"
        }}
        """

        messages = [
            {"role": "system", "content": system_message_content},
            {"role": "user", "content": user_message_content}
        ]

        short_title, summary, chosen_method, success = self._call_ai_api(messages)

        if not success:
            print("AI text processing failed. Using truncated original description as fallback for summary.")
            fallback_summary = ' '.join(description.split()[:SUMMARY_MAX_WORDS])
            font_summary = load_font(FONT_PATH_REGULAR, FONT_SIZE_SUMMARY)
            wrapped_fallback = wrap_text_by_word_count(fallback_summary, font_summary, CANVAS_WIDTH - (LEFT_PADDING + RIGHT_PADDING), max_words=SUMMARY_MAX_WORDS)
            final_summary = ' '.join(wrapped_fallback)

            final_short_title = ' '.join(title.split()[:TITLE_MAX_WORDS])
            return final_short_title, final_summary, "Fallback", False

        return short_title, summary, chosen_method, True


class CaptionGenerator:
    """Generates Instagram captions and hashtags using OpenRouter AI (Mistral model)."""

    def __init__(self):
        self.api_key = OPENROUTER_MISTRAL_API_KEY
        self.model = OPENROUTER_MISTRAL_MODEL
        self.site_url = OPENROUTER_SITE_URL
        self.site_name = OPENROUTER_SITE_NAME
        self.client = OpenAI(
            base_url="https://openrouter.ai/api/v1",
            api_key=self.api_key,
        )

    def generate_caption_and_hashtags(self, short_title, summary, storytelling_method, post_type, style_recommendations=""):
        """
        Generates an Instagram-style caption and 10 relevant hashtags.
        Returns (caption, hashtags_list, success_flag).
        """
        if self.api_key == "sk-or-v1-YOUR_MISTRAL_SMALL_API_KEY_HERE":
            print("OPENROUTER_MISTRAL_API_KEY is a placeholder. Skipping caption/hashtag generation.")
            return "Generated caption fallback.", ["#news", "#update"], False

        # Custom prompt for motivational quotes
        if post_type == 'motivational_quote_post':
            system_message_content = f"""
            You are a highly engaging social media manager specializing in inspirational content for entrepreneurs, business leaders, and innovators.
            Your task is to generate a concise, uplifting Instagram caption and exactly 10 trending, relevant hashtags for a motivational quote.
            The caption should encourage reflection, positivity, and action, making it relatable to the challenges and triumphs in business, startups, and technology.
            The hashtags should be highly relevant to motivation, business, startups, finance, and entrepreneurship.
            The output MUST be a valid JSON object with keys "caption" (string) and "hashtags" (array of strings).
            """
            user_message_content = f"""
            Generate an Instagram caption and 10 relevant hashtags.
            Quote: "{short_title}" (Note: short_title is used to pass the quote text for quote posts)
            Author: "{summary}" (Note: summary is used to pass the author for quote posts)

            Return ONLY the JSON object with two keys: "caption" and "hashtags".
            Example: {{"caption": "Example quote caption...", "hashtags": ["#motivation", "#dailyquote"]}}
            """
        else: # Original prompt for news posts
            system_message_content = f"""
            You are a creative social media manager specializing in Instagram posts for news, especially Startup, Business, Financial, and Entrepreneurial content.
            Your task is to generate a concise and engaging Instagram caption and exactly 10 trending, relevant hashtags based on a news title and summary, taking into account the specific storytelling method used.
            The caption should be evocative, encourage engagement, and align with the storytelling method (e.g., if it's a "What If" scenario, the caption should play into that).
            The hashtags should be highly relevant to the topic and popular.
            The output MUST be a valid JSON object with keys "caption" (string) and "hashtags" (array of strings).
            Consider the following style recommendations from past performance analysis when generating the content: {style_recommendations}
            """
            user_message_content = f"""
            Generate an Instagram caption and 10 relevant hashtags.

            News Headline (Storytelling focused): {short_title}
            News Summary: {summary}
            Storytelling Method Used: {storytelling_method}

            Return ONLY the JSON object with two keys: "caption" and "hashtags".
            Example: {{"caption": "Example caption...", "hashtags": ["#example", "#trending"]}}
            """


        messages = [
            {"role": "system", "content": system_message_content},
            {"role": "user", "content": user_message_content}
        ]

        try:
            completion = self.client.chat.completions.create(
                extra_headers={
                    "HTTP-Referer": self.site_url,
                    "X-Title": self.site_name,
                },
                model=self.model,
                messages=messages,
                temperature=0.7,
                max_tokens=250,
                response_format={"type": "json_object"}
            )

            if completion.choices and completion.choices[0].message and completion.choices[0].message.content:
                ai_content_str = completion.choices[0].message.content
                try:
                    parsed_data = json.loads(ai_content_str)
                    caption = parsed_data.get('caption', "Engaging caption from Mistral.")
                    hashtags = parsed_data.get('hashtags', [])
                    if not isinstance(hashtags, list) or not all(isinstance(h, str) for h in hashtags):
                        hashtags = ["#news", "#update"]

                    if len(hashtags) > 10:
                        hashtags = hashtags[:10]
                    elif len(hashtags) < 10:
                        generic_hashtags = ["#dailynews", "#breaking", "#insightpulse", "#info", "#currentaffairs",
                                            "#innovation", "#businessinsights", "#financefacts", "#startupjourney",
                                            "#entrepreneurmindset", "#successstories", "#marketupdate", "#investing",
                                            "#businesstips", "#futureofwork"]
                        # Filter to avoid duplicates and ensure a good mix
                        current_tags_lower = {h.lower() for h in hashtags}
                        for gen_tag in generic_hashtags:
                            if len(hashtags) >= 10:
                                break
                            if gen_tag.lower() not in current_tags_lower:
                                hashtags.append(gen_tag)
                                current_tags_lower.add(gen_tag.lower())

                    hashtags = [h if h.startswith('#') else f'#{h}' for h in hashtags]

                    return caption, hashtags, True
                except json.JSONDecodeError:
                    print(f"Warning: Mistral did not return valid JSON for caption/hashtags. Raw: {ai_content_str[:200]}...")
                    return "Caption generation failed due to invalid JSON from AI.", ["#error", "#news"], False

            print(f"Mistral response missing expected content for caption/hashtags: {completion}")
            return "Caption generation failed: AI response structure invalid.", ["#error", "#news"], False

        except Exception as e:
            print(f"Error calling Mistral API for caption/hashtags: {e}")
            return f"Caption generation failed: {e}", ["#api_error", "#news"], False


class ImageFetcher:
    """Fetches images from Pexels, Unsplash, Openverse, and Pixabay based on text prompts."""

    def __init__(self):
        self.pexels_api_key = PEXELS_API_KEY
        self.pexels_api_url = PEXELS_API_URL
        self.unsplash_access_key = UNSPLASH_ACCESS_KEY
        self.unsplash_api_url = UNSPLASH_API_URL
        self.openverse_api_url = OPENVERSE_API_URL
        self.pixabay_api_key = PIXABAY_API_KEY
        self.pixabay_api_url = PIXABAY_API_URL

    def _fetch_from_pexels(self, prompt, width, height):
        try:
            if self.pexels_api_key == "YOUR_PEXELS_API_KEY_HERE":
                print("PEXELS_API_KEY is a placeholder. Skipping Pexels.")
                return None
            headers = {"Authorization": self.pexels_api_key}
            params = {"query": prompt, "orientation": "portrait", "size": "large", "per_page": 1}
            print(f"Searching Pexels for image with prompt: {prompt[:50]}...")
            response = requests.get(f"{self.pexels_api_url}/search", headers=headers, params=params, timeout=15)
            response.raise_for_status()
            data = response.json()
            if data and data['photos']:
                image_url = data['photos'][0]['src']['original']
                print(f"Found image on Pexels: {image_url}")
                img_data = requests.get(image_url, stream=True, timeout=15)
                img_data.raise_for_status()
                return Image.open(io.BytesIO(img_data.content))
            return None
        except requests.exceptions.Timeout:
            print(f"Pexels API request timed out for prompt '{prompt[:50]}...'.")
            return None
        except requests.exceptions.RequestException as e:
            print(f"Error fetching from Pexels: {e}")
            return None
        except Exception as e:
            print(f"An unexpected error occurred during Pexels fetch: {e}")
            return None

    def _fetch_from_unsplash(self, prompt, width, height):
        try:
            if self.unsplash_access_key == "YOUR_UNSPLASH_ACCESS_KEY_HERE":
                print("UNSPLASH_ACCESS_KEY is a placeholder. Skipping Unsplash.")
                return None
            params = {"query": prompt, "orientation": "portrait", "client_id": self.unsplash_access_key, "per_page": 1}
            print(f"Searching Unsplash for image with prompt: {prompt[:50]}...")
            response = requests.get(f"{self.unsplash_api_url}/search/photos", params=params, timeout=15)
            response.raise_for_status()
            data = response.json()
            if data and data['results']:
                image_url = data['results'][0]['urls']['regular']
                print(f"Found image on Unsplash: {image_url}")
                img_data = requests.get(image_url, stream=True, timeout=15)
                img_data.raise_for_status()
                return Image.open(io.BytesIO(img_data.content))
            return None
        except requests.exceptions.Timeout:
            print(f"Unsplash API request timed out for prompt '{prompt[:50]}...'.")
            return None
        except requests.exceptions.RequestException as e:
            print(f"Error fetching from Unsplash: {e}")
            return None
        except Exception as e:
            print(f"An unexpected error occurred during Unsplash fetch: {e}")
            return None

    def _fetch_from_openverse(self, prompt, width, height):
        try:
            params = {"q": prompt, "license_type": "commercial", "image_type": "photo", "orientation": "portrait", "page_size": 1}
            print(f"Searching Openverse for image with prompt: {prompt[:50]}...")
            response = requests.get(self.openverse_api_url, params=params, timeout=15)
            response.raise_for_status()
            data = response.json()
            if data and data['results']:
                image_url = data['results'][0]['url']
                print(f"Found image on Openverse: {image_url}")
                img_data = requests.get(image_url, stream=True, timeout=15)
                img_data.raise_for_status()
                return Image.open(io.BytesIO(img_data.content))
            return None
        except requests.exceptions.Timeout:
            print(f"Openverse API request timed out for prompt '{prompt[:50]}...'.")
            return None
        except requests.exceptions.RequestException as e:
            print(f"Error fetching from Openverse: {e}")
            return None
        except Exception as e:
            print(f"An unexpected error occurred during Openverse fetch: {e}")
            return None

    def _fetch_from_pixabay(self, prompt, width, height):
        try:
            if self.pixabay_api_key == "YOUR_PIXABAY_API_KEY_HERE":
                print("PIXABAY_API_KEY is a placeholder. Skipping Pixabay.")
                return None
            params = {"key": self.pixabay_api_key, "q": prompt, "image_type": "photo", "orientation": "vertical", "safesearch": "true", "per_page": 1, "editors_choice": "true", "min_width": width, "min_height": height}
            print(f"Searching Pixabay for image with prompt: {prompt[:50]}...")
            response = requests.get(self.pixabay_api_url, params=params, timeout=15)
            response.raise_for_status()
            data = response.json()
            if data and data['hits']:
                image_url = data['hits'][0].get('largeImageURL') or data['hits'][0].get('webformatURL')
                if image_url:
                    print(f"Found image on Pixabay: {image_url}")
                    img_data = requests.get(image_url, stream=True, timeout=15)
                    img_data.raise_for_status()
                    return Image.open(io.BytesIO(img_data.content))
            return None
        except requests.exceptions.Timeout:
            print(f"Pixabay API request timed out for prompt '{prompt[:50]}...'.")
            return None
        except requests.exceptions.RequestException as e:
            print(f"Error fetching from Pixabay: {e}")
            return None
        except Exception as e:
            print(f"An unexpected error occurred during Pixabay fetch: {e}")
            return None

    def fetch_image(self, prompt, width=IMAGE_DISPLAY_WIDTH, height=IMAGE_DISPLAY_HEIGHT):
        # Image fetching is only for news content. Motivational quote posts use a generated background.
        if "motivational quote" in prompt.lower() or "inspirational quote" in prompt.lower():
            return None # Indicate no image is needed to be fetched for quotes

        fetched_image = None
        fetched_image = self._fetch_from_pexels(prompt, width, height)
        if fetched_image is None:
            fetched_image = self._fetch_from_unsplash(prompt, width, height)
        if fetched_image is None:
            fetched_image = self._fetch_from_openverse(prompt, width, height)
        if fetched_image is None:
            fetched_image = self._fetch_from_pixabay(prompt, width, height)
        return fetched_image


class ImageLocalProcessor:
    """Handles local image processing and text overlays with new design aesthetics."""

    # REMOVED: MOTIVATIONAL_QUOTES static list, as it will be AI-generated

    def _get_filtered_source_display(self, original_source_text: str) -> str:
        """
        Filters and shortens the source text for internal logging/metadata.
        This function is no longer used for display on the post itself.
        """
        if not original_source_text:
            return "UNKNOWN"

        source_map = {
            "SYSTEM": "SYSTEM",
            "TECHCRUNCH STARTUPS": "TECHCRUNCH",
            "FORBES INNOVATION": "FORBES",
            "INC. MAGAZINE": "INC.",
            "ENTREPRENEUR MAGAZINE": "ENTREPRENEUR",
            "WIRED BUSINESS": "WIRED",
            "SIFTED EU STARTUPS": "SIFTED",
            "STARTUP GRIND BLOG": "STARTUP GRIND",
            "VENTUREBEAT STARTUP": "VENTUREBEAT",
            "REUTERS BUSINESS NEWS": "REUTERS BUSINESS",
            "WALL STREET JOURNAL BUSINESS": "WSJ BUSINESS",
            "CNBC BUSINESS NEWS": "CNBC",
            "BLOOMBERG BUSINESSWEEK": "BLOOMBERG BW",
            "HARVARD BUSINESS REVIEW": "HBR",
            "FINANCIAL TIMES COMPANIES": "FT COMPANIES",
            "BUSINESS INSIDER": "BUSINESS INSIDER",
            "THE GUARDIAN BUSINESS": "GUARDIAN BIZ",
            "REUTERS MARKETS NEWS": "REUTERS MARKETS",
            "DOW JONES NEWS (FINANCIAL)": "DOW JONES",
            "FINANCIAL TIMES MARKETS": "FT MARKETS",
            "INVESTING.COM NEWS": "INVESTING.COM",
            "BLOOMBERG MARKETS": "BLOOMBERG MARKETS",
            "SEEKING ALPHA": "SEEKING ALPHA",
            "MARKETWATCH TOP STORIES": "MARKETWATCH",
            "INVESTOPEDIA": "INVESTOPEDIA",
            "BUSINESS INSIDER STARTUPS (ENTREPRENEUR)": "BUSINESS INSIDER STARTUPS",
            "FAST COMPANY (ENTREPRENEURSHIP)": "FAST COMPANY",
            "STARTUPS.CO.UK": "STARTUPS.CO.UK",
            "FOUNDR MAGAZINE": "FOUNDR",
            "Y COMBINATOR BLOG": "Y COMBINATOR",
        }

        mapped_source = source_map.get(original_source_text.upper().strip())
        if mapped_source:
            return mapped_source

        processed_source = original_source_text.upper().strip()

        noisy_phrases = [
            r'\bNEWS\b', r'\bREPORTS\b', r'\bLIVE\b', r'\bUPDATE\b', r'\bVIDEO FROM\b',
            r'\bBREAKING\b', r'\bGLOBAL\b', r'\bWORLD\b', r'\bINDIA\b', r'\bTHE\b',
            r'\bCOM\b', r'\.COM', r'\.ORG', r'\.NET', r'\.IN', r'\.CO\.IN',
            r'INTERNATIONAL EDITION', r'LATEST TODAY', r'CORRESPONDENT', r'CHANNEL', r'TV', r'PRESS',
            r'\bMAGAZINE\b', r'\bBUSINESS\b', r'\bFINANCIAL\b', r'\bJOURNAL\b', r'\bPRESS\b',
            r'\bDAILY\b', r'\bWEEKLY\b', r'\bMONTHLY\b', r'\bINSIGHTS\b', r'\bSPOTLIGHT\b',
            r'\bARTICLE\b', r'\bBLOG\b'
        ]

        for phrase in noisy_phrases:
            processed_source = re.sub(phrase, '', processed_source).strip()

        processed_source = re.sub(r'\s+', ' ', processed_source).strip()

        words = processed_source.split()
        if len(words) <= 3 and len(words) > 0:
            return processed_source
        elif words:
            return ' '.join(words[:3])

        return "UNKNOWN"


    def overlay_text(self, base_pil_image, post_data):
        """
        Creates the final post image with different layouts based on content type.
        """
        content_type = post_data.get('content_type_display', 'general_news').lower()
        final_canvas = None
        draw = None
        dummy_draw_for_text_bbox = ImageDraw.Draw(Image.new('RGB', (1,1)))

        try: # Outer try-except for the entire overlay_text function
            if content_type == 'motivational_quote_post':
                # --- Layout for Motivational Quote Post ---
                quote_text = post_data.get('title', 'No Quote') # Title field holds the quote for quote posts
                quote_author = post_data.get('summary', 'Unknown') # Summary field holds the author for quote posts

                # Use quote-specific colors for background
                background_gen = BackgroundGenerator()
                # Creating a subtle gradient for quotes too, using the new colors
                final_canvas = background_gen.generate_gradient_background(CANVAS_WIDTH, CANVAS_HEIGHT,
                                                                            QUOTE_COLOR_BACKGROUND_LIGHT,
                                                                            tuple(int(c * 0.9) for c in QUOTE_COLOR_BACKGROUND_LIGHT[:3]) + (255,)) # Slightly darker variant for gradient
                draw = ImageDraw.Draw(final_canvas)

                # Draw the main quote text
                font_quote = load_font(FONT_PATH_ALFA_SLAB_ONE, FONT_SIZE_QUOTE) # Alfa Slab One for prominent quote
                text_area_width = CANVAS_WIDTH - (2 * LEFT_PADDING)
                wrapped_quote_lines = textwrap.wrap(quote_text, width=int(text_area_width / (FONT_SIZE_QUOTE * 0.5)), break_long_words=False)

                total_quote_height = 0
                for line in wrapped_quote_lines:
                    line_bbox = dummy_draw_for_text_bbox.textbbox((0,0), line, font=font_quote)
                    total_quote_height += (line_bbox[3] - line_bbox[1]) + 15 # Increased line spacing for quote


                # Center the quote vertically and horizontally
                current_y = (CANVAS_HEIGHT - total_quote_height) // 2
                
                # Adjust to ensure it's not too high for very short quotes
                if current_y < TOP_PADDING + 50:
                    current_y = TOP_PADDING + 50


                for line in wrapped_quote_lines:
                    line_bbox = dummy_draw_for_text_bbox.textbbox((0,0), line, font=font_quote)
                    line_width = line_bbox[2] - line_bbox[0]
                    text_x_centered = (CANVAS_WIDTH - line_width) // 2
                    draw.text((text_x_centered, current_y), line, font=font_quote, fill=QUOTE_COLOR_TEXT_DARK)
                    current_y += (line_bbox[3] - line_bbox[1]) + 15 # Consistent line spacing


                # Draw author below quote
                if quote_author and quote_author != "Unknown":
                    font_author = load_font(FONT_PATH_REGULAR, FONT_SIZE_QUOTE_AUTHOR) # Montserrat Regular for author
                    author_bbox = dummy_draw_for_text_bbox.textbbox((0,0), quote_author, font=font_author)
                    author_width = author_bbox[2] - author_bbox[0]
                    draw.text(((CANVAS_WIDTH - author_width) // 2, current_y + 40), # More margin below quote
                              quote_author, font=font_author, fill=QUOTE_COLOR_ACCENT)


                # Logo for Quote Post (bottom center)
                try:
                    logo_image = Image.open(LOGO_PATH).convert("RGBA")
                    logo_image.thumbnail((QUOTE_LOGO_WIDTH, QUOTE_LOGO_HEIGHT), Image.Resampling.LANCZOS)
                    logo_x = (CANVAS_WIDTH - QUOTE_LOGO_WIDTH) // 2
                    logo_y = CANVAS_HEIGHT - QUOTE_LOGO_BOTTOM_MARGIN - QUOTE_LOGO_HEIGHT
                    # FIX: Use final_canvas.paste, not draw.paste
                    final_canvas.paste(logo_image, (logo_x, logo_y), logo_image)
                except FileNotFoundError:
                    print(f"Warning: Logo file not found at {LOGO_PATH}. Skipping logo for quote post.")
                    # FIX: Removed the "Insight Pulse" text fallback here as requested
                except Exception as e:
                    print(f"Error embedding logo for quote post: {e}. Skipping logo for quote post.")
                    # FIX: Removed the "Insight Pulse" text fallback here as requested


            else:
                # --- Original Layout for News Posts ---
                # 1. Create Gradient Background
                background_gen = BackgroundGenerator()
                final_canvas = background_gen.generate_gradient_background(CANVAS_WIDTH, CANVAS_HEIGHT,
                                                                            COLOR_GRADIENT_TOP_LEFT, COLOR_GRADIENT_BOTTOM_RIGHT)
                draw = ImageDraw.Draw(final_canvas)

                # --- TOP LEFT CATEGORY TEXT ---
                content_type_map = {
                    'startup_news': "STARTUP INSIGHTS",
                    'business_news': "BUSINESS PULSE",
                    'financial_news': "FINANCIAL FOCUS",
                    'entrepreneurial_news': "ENTREPRENEUR VISION",
                }
                content_type_display = content_type_map.get(content_type, "INSIGHT PULSE")

                font_top_left_text = load_font(FONT_PATH_ALFA_SLAB_ONE, FONT_SIZE_TOP_LEFT_TEXT)
                draw.text((TOP_LEFT_TEXT_POS_X, TOP_LEFT_TEXT_POS_Y), content_type_display, font=font_top_left_text, fill=COLOR_TOP_LEFT_TEXT)


                # --- TIMESTAMP (TOP RIGHT) ---
                timestamp_text = datetime.now().strftime("%d %b %Y | %H:%M")
                font_timestamp = load_font(FONT_PATH_REGULAR, FONT_SIZE_TIMESTAMP)
                timestamp_bbox = dummy_draw_for_text_bbox.textbbox((0,0), timestamp_text, font=font_timestamp)
                timestamp_width = timestamp_bbox[2] - timestamp_bbox[0]

                draw.text((TIMESTAMP_POS_X_RIGHT_ALIGN - timestamp_width, TIMESTAMP_POS_Y),
                          timestamp_text, font=font_timestamp, fill=COLOR_TIMESTAMP_TEXT)

                # --- NEWS IMAGE (CENTERED, ROUNDED CORNERS) ---
                image_start_y = max(
                    TOP_LEFT_TEXT_POS_Y + (dummy_draw_for_text_bbox.textbbox((0,0), content_type_display, font=font_top_left_text)[3] - dummy_draw_for_text_bbox.textbbox((0,0), content_type_display, font=font_top_left_text)[1]),
                    TIMESTAMP_POS_Y + (timestamp_bbox[3] - timestamp_bbox[1])
                ) + IMAGE_TOP_MARGIN_FROM_TOP_ELEMENTS

                target_aspect_ratio = IMAGE_DISPLAY_WIDTH / IMAGE_DISPLAY_HEIGHT
                generated_aspect_ratio = base_pil_image.width / base_pil_image.height

                if generated_aspect_ratio > target_aspect_ratio:
                    new_width = int(base_pil_image.height * target_aspect_ratio)
                    left = (base_pil_image.width - new_width) / 2
                    top = 0
                    right = (base_pil_image.width + new_width) / 2
                    bottom = base_pil_image.height
                else:
                    new_height = int(base_pil_image.width / target_aspect_ratio)
                    left = 0
                    top = (base_pil_image.height - new_height) / 2
                    right = base_pil_image.width
                    bottom = (base_pil_image.height + new_height) / 2

                cropped_image = base_pil_image.crop((left, top, right, bottom))
                news_image_for_display = cropped_image.resize((IMAGE_DISPLAY_WIDTH, IMAGE_DISPLAY_HEIGHT), Image.Resampling.LANCZOS)

                temp_img = Image.new("RGBA", news_image_for_display.size, (0, 0, 0, 0))
                temp_draw = ImageDraw.Draw(temp_img)
                shadow_offset = 8
                shadow_color = (0, 0, 0, 80)
                temp_draw.rounded_rectangle(
                    (shadow_offset, shadow_offset, IMAGE_DISPLAY_WIDTH + shadow_offset, IMAGE_DISPLAY_HEIGHT + shadow_offset),
                    radius=IMAGE_ROUND_RADIUS, fill=shadow_color
                )
                shadow_img = temp_img.filter(ImageFilter.GaussianBlur(radius=8))

                mask = Image.new('L', (IMAGE_DISPLAY_WIDTH, IMAGE_DISPLAY_HEIGHT), 0)
                mask_draw = ImageDraw.Draw(mask)
                mask_draw.rounded_rectangle((0, 0, IMAGE_DISPLAY_WIDTH, IMAGE_DISPLAY_HEIGHT),
                                            radius=IMAGE_ROUND_RADIUS, fill=255)

                news_image_x = (CANVAS_WIDTH - IMAGE_DISPLAY_WIDTH) // 2
                
                final_canvas.paste(shadow_img, (news_image_x, int(image_start_y)), shadow_img)
                final_canvas.paste(news_image_for_display, (news_image_x, int(image_start_y)), mask)


                # --- TITLE (BELOW IMAGE) ---
                title_text_raw = str(post_data.get('title', 'NO TITLE')).upper()
                font_headline = load_font(FONT_PATH_ALFA_SLAB_ONE, FONT_SIZE_HEADLINE)

                text_area_width = CANVAS_WIDTH - (LEFT_PADDING + RIGHT_PADDING)
                wrapped_title_lines = wrap_text_by_word_count(title_text_raw, font_headline, text_area_width, max_words=TITLE_MAX_WORDS)

                current_y_title = image_start_y + IMAGE_DISPLAY_HEIGHT + TITLE_TOP_MARGIN_FROM_IMAGE

                for line in wrapped_title_lines:
                    line_bbox = dummy_draw_for_text_bbox.textbbox((0,0), line, font=font_headline)
                    line_width = line_bbox[2] - line_bbox[0]

                    text_x_centered = (CANVAS_WIDTH - line_width) / 2
                    draw.text((text_x_centered, current_y_title), line, font=font_headline, fill=COLOR_HEADLINE_TEXT)
                    current_y_title += (line_bbox[3] - line_bbox[1]) + TITLE_LINE_SPACING

                # --- SUMMARY TEXT (BELOW TITLE) - Dynamically positioned ---
                summary_text_raw = str(post_data.get('summary', 'No summary provided.')).replace("&#x27;", "'").replace("&quot;", "\"")
                font_summary = load_font(FONT_PATH_TAPESTRY, FONT_SIZE_SUMMARY)

                wrapped_summary_lines = wrap_text_by_word_count(summary_text_raw, font_summary,
                                                               CANVAS_WIDTH - (LEFT_PADDING + RIGHT_PADDING),
                                                               max_words=SUMMARY_MAX_WORDS)
                if len(wrapped_summary_lines) > SUMMARY_MAX_LINES:
                    wrapped_summary_lines = wrapped_summary_lines[:SUMMARY_MAX_LINES]
                    wrapped_summary_lines[-1] = wrapped_summary_lines[-1].strip() + "..."

                current_y_summary = current_y_title + SUMMARY_TOP_MARGIN_FROM_TITLE

                for line in wrapped_summary_lines:
                    draw.text((LEFT_PADDING, current_y_summary), line, font=font_summary, fill=COLOR_SUMMARY_TEXT)
                    line_height = (dummy_draw_for_text_bbox.textbbox((0,0), line, font=font_summary)[3] - dummy_draw_for_text_bbox.textbbox((0,0), line, font=font_summary)[1])
                    current_y_summary += line_height + SUMMARY_LINE_SPACING

                current_y_summary -= SUMMARY_LINE_SPACING # Remove last line spacing

                # --- DIVIDER LINE ---
                divider_y = current_y_summary + DIVIDER_Y_OFFSET_FROM_SUMMARY
                draw.line([(LEFT_PADDING, divider_y), (CANVAS_WIDTH - RIGHT_PADDING, divider_y)], fill=COLOR_DIVIDER_LINE, width=DIVIDER_LINE_THICKNESS)


                # --- LOGO (BOTTOM LEFT) - Adjusted positioning for news posts ---
                logo_final_y = CANVAS_HEIGHT - BOTTOM_PADDING - LOGO_HEIGHT - LOGO_BOTTOM_MARGIN
                # Ensure logo is below divider with some padding, if space allows.
                logo_final_y = max(logo_final_y, divider_y + 20) # 20px buffer below divider

                try:
                    logo_image = Image.open(LOGO_PATH).convert("RGBA")
                    logo_image.thumbnail((LOGO_WIDTH, LOGO_HEIGHT), Image.Resampling.LANCZOS)
                    final_canvas.paste(logo_image, (LEFT_PADDING, int(logo_final_y)), logo_image)

                except FileNotFoundError:
                    print(f"Warning: Logo file not found at {LOGO_PATH}. Embedding text fallback.")
                    draw.text((LEFT_PADDING, int(logo_final_y) + (LOGO_HEIGHT - 30) // 2), "Insight Pulse", font=load_font(FONT_PATH_BOLD, 30), fill=COLOR_SOURCE_TEXT)
                except Exception as e:
                    print(f"Error embedding logo: {e}. Embedding text fallback.")
                    draw.text((LEFT_PADDING, int(logo_final_y) + (LOGO_HEIGHT - 30) // 2), "Insight Pulse (Error)", font=load_font(FONT_PATH_BOLD, 30), fill=COLOR_SOURCE_TEXT)


            # --- Add Thin Border Line at edges of the post (for both types) ---
            if final_canvas: # Ensure canvas was created
                border_rect = [(BORDER_THICKNESS // 2, BORDER_THICKNESS // 2),
                               (CANVAS_WIDTH - BORDER_THICKNESS // 2, CANVAS_HEIGHT - BORDER_THICKNESS // 2)]
                draw.rectangle(border_rect, outline=BORDER_COLOR, width=BORDER_THICKNESS)


            return final_canvas

        except Exception as e:
            print(f"Error during image overlay and composition: {e}")
            import traceback
            traceback.print_exc()
            img_error = Image.new('RGB', (CANVAS_WIDTH, CANVAS_HEIGHT), color = (50, 50, 50))
            draw_error = ImageDraw.Draw(img_error)
            error_font = load_font(FONT_PATH_REGULAR, 40)
            draw_error.text((50, CANVAS_HEIGHT // 2 - 20), "IMAGE COMPOSITION ERROR", font=error_font, fill=(255,0,0))
            draw_error.text((50, CANVAS_HEIGHT // 2 + 30), f"Check API keys or prompt: {str(e)[:100]}...", font=load_font(FONT_PATH_REGULAR, 20), fill=(255,255,255))
            return img_error


class CloudinaryUploader:
    """Handles uploading images to Cloudinary."""

    def __init__(self):
        cloudinary.config(
            cloud_name=CLOUDINARY_CLOUD_NAME,
            api_key=CLOUDINARY_API_KEY,
            api_secret=CLOUDINARY_API_SECRET
        )

    def upload_image(self, image_path, public_id, folder="news_posts"):
        """
        Uploads an image to Cloudinary.
        image_path: local path to the image file.
        public_id: A unique identifier for the image in Cloudinary.
        folder: The folder in Cloudinary to upload to.
        Returns the secure URL of the uploaded image or None on failure.
        """
        try:
            if CLOUDINARY_CLOUD_NAME == "YOUR_CLOUDINARY_CLOUD_NAME_HERE":
                print("Cloudinary credentials are placeholders. Skipping upload.")
                return None

            print(f"Uploading {image_path} to Cloudinary folder '{folder}' with public_id '{public_id}'...")
            upload_result = cloudinary.uploader.upload(
                image_path,
                public_id=public_id,
                folder=folder
            )
            secure_url = upload_result.get('secure_url')
            if secure_url:
                print(f"Image uploaded to Cloudinary: {secure_url}")
                return secure_url
            else:
                print(f"Cloudinary upload failed: No secure_url in response. Result: {upload_result}")
                return None
        except Exception as e:
            print(f"Error uploading image to Cloudinary: {e}")
            return None


class InstagramPoster:
    """Handles posting images to Instagram via the Facebook Graph API."""

    def __init__(self):
        self.access_token = FB_PAGE_ACCESS_TOKEN
        self.instagram_business_account_id = INSTAGRAM_BUSINESS_ACCOUNT_ID
        self.graph_api_base_url = "https://graph.facebook.com/v19.0/"

    def post_image(self, image_url, caption):
        """
        Posts an image to Instagram.
        image_url: The secure URL of the image from Cloudinary.
        caption: The combined caption and hashtags.
        Returns True on success, False on failure.
        """
        if self.instagram_business_account_id == "YOUR_INSTAGRAM_BUSINESS_ACCOUNT_ID_HERE" or \
           self.access_token == "YOUR_FB_PAGE_ACCESS_TOKEN_HERE":
            print("Instagram Graph API credentials are placeholders. Skipping Instagram post.")
            return False

        if not image_url:
            print("No image URL provided for Instagram post. Skipping.")
            return False

        print(f"Attempting to post to Instagram (Account ID: {self.instagram_business_account_id})...")

        # Step 1: Create media container
        media_container_url = f"{self.graph_api_base_url}{self.instagram_business_account_id}/media"
        media_params = {
            'image_url': image_url,
            'caption': caption,
            'access_token': self.access_token
        }
        try:
            response = requests.post(media_container_url, params=media_params, timeout=30)
            response.raise_for_status()
            media_container_id = response.json().get('id')
            print(f"Media container created with ID: {media_container_id}")
        except requests.exceptions.Timeout:
            print(f"Error: Instagram API (media container) request timed out. Image URL: {image_url}")
            return False
        except requests.exceptions.RequestException as e:
            print(f"Error creating Instagram media container: {e}. Response: {response.json() if 'response' in locals() else 'N/A'}")
            return False
        except Exception as e:
            print(f"An unexpected error occurred during Instagram media container creation: {e}")
            return False

        if not media_container_id:
            print("Failed to get media container ID.")
            return False

        # Step 2: Publish media container
        publish_url = f"{self.graph_api_base_url}{self.instagram_business_account_id}/media_publish"
        publish_params = {
            'creation_id': media_container_id,
            'access_token': self.access_token
        }
        try:
            response = requests.post(publish_url, params=publish_params, timeout=30)
            response.raise_for_status()
            post_id = response.json().get('id')
            if post_id:
                print(f"Post successfully published to Instagram with ID: {post_id}")
                return True
            else:
                print(f"Instagram publish failed: No post ID in response. Result: {response.json()}")
                return False
        except requests.exceptions.Timeout:
            print(f"Error: Instagram API (media publish) request timed out for container ID: {media_container_id}")
            return False
        except requests.exceptions.RequestException as e:
            print(f"Error publishing to Instagram: {e}. Response: {response.json() if 'response' in locals() else 'N/A'}")
            return False
        except Exception as e:
            print(f"An unexpected error occurred during Instagram publish: {e}")
            return False


class LocalSaver:
    """Saves data and images locally to JSON and Excel."""

    def __init__(self, image_output_dir, json_output_dir, excel_output_dir, all_posts_json_file, all_posts_excel_file):
        self.IMAGE_OUTPUT_DIR = image_output_dir
        self.JSON_OUTPUT_DIR = json_output_dir
        self.EXCEL_OUTPUT_DIR = excel_output_dir
        self.ALL_POSTS_JSON_FILE = all_posts_json_file
        self.ALL_POSTS_EXCEL_FILE = all_posts_excel_file
        os.makedirs(self.IMAGE_OUTPUT_DIR, exist_ok=True)
        os.makedirs(self.JSON_OUTPUT_DIR, exist_ok=True)
        os.makedirs(self.EXCEL_OUTPUT_DIR, exist_ok=True)

    def save_post(self, post_data, workflow_manager_instance): # Modified to accept workflow_manager_instance
        """Saves a single post's data and image."""
        post_type_label = post_data.get('type', 'post').replace('_', '-')
        timestamp_str = datetime.now().strftime("%Y%m%d_%H%M%S")
        # Use the passed workflow_manager_instance to get the post number
        post_id = f"{post_type_label}_{timestamp_str}_post-{workflow_manager_instance.get_current_post_number()}"

        post_data['Post_ID'] = post_id

        image_filename = f"{post_id}.png"
        image_path = os.path.join(self.IMAGE_OUTPUT_DIR, image_filename)

        if 'final_image' in post_data and isinstance(post_data['final_image'], Image.Image):
            try:
                post_data['final_image'].save(image_path)
                print(f"Image saved to: {image_path}")
            except Exception as e:
                print(f"Error saving image to {image_path}: {e}")
                image_path = "Error saving image"
        else:
            print(f"Warning: No valid 'final_image' found in post_data for post ID {post_id}. Image not saved.")
            image_path = "No image generated/saved"

        # Dynamically add metadata based on post type
        metadata = {
            "Post_ID": post_data['Post_ID'],
            "SEO_Caption": post_data.get('seo_caption'),
            "Hashtags": ', '.join(post_data.get('hashtags', [])),
            "Local_Image_Path": image_path,
            "Cloudinary_URL": post_data.get('cloudinary_url', 'N/A'),
            "Instagram_Posted": post_data.get('instagram_posted', False),
            "Timestamp": datetime.now(UTC).isoformat(),
            "Source_Type": post_data.get('type'),
        }

        if post_data.get('type') == 'motivational_quote_post':
            metadata.update({
                "Quote_Text": post_data.get('quote_text'),
                "Quote_Author": post_data.get('quote_author'),
            })
        else:
            metadata.update({
                "Title": post_data.get('title'),
                "Summary": post_data.get('summary'),
                "Storytelling_Method": post_data.get('storytelling_method', 'N/A'),
                "Source_URL": post_data.get('url', ''),
                "Original_Source": post_data.get('source', 'N/A'),
                "Original_Description": post_data.get('original_description', 'N/A')
            })

        try:
            existing_data = []
            if os.path.exists(self.ALL_POSTS_JSON_FILE):
                with open(self.ALL_POSTS_JSON_FILE, 'r', encoding='utf-8') as f:
                    try:
                        existing_data = json.load(f)
                        if not isinstance(existing_data, list):
                            existing_data = []
                    except json.JSONDecodeError:
                        print(f"Warning: {self.ALL_POSTS_JSON_FILE} is corrupted. Starting with empty JSON list.")
                        existing_data = []

            existing_data.append(metadata)

            with open(self.ALL_POSTS_JSON_FILE, 'w', encoding='utf-8') as f:
                json.dump(existing_data, f, indent=4)
            print(f"Metadata appended to: {self.ALL_POSTS_JSON_FILE}")
        except Exception as e:
            print(f"Error saving to JSON file {self.ALL_POSTS_JSON_FILE}: {e}")

        try:
            df = pd.DataFrame([metadata])
            if os.path.exists(self.ALL_POSTS_EXCEL_FILE):
                with pd.ExcelWriter(self.ALL_POSTS_EXCEL_FILE, mode='a', engine='openpyxl', if_sheet_exists='overlay') as writer:
                    sheet_exists_and_has_data = False
                    if 'Posts' in writer.sheets:
                        if writer.sheets['Posts'].max_row > 1:
                            sheet_exists_and_has_data = True

                    if sheet_exists_and_has_data:
                        df.to_excel(writer, sheet_name='Posts', index=False, header=False, startrow=writer.sheets['Posts'].max_row)
                    else:
                        df.to_excel(writer, sheet_name='Posts', index=False, header=True)
            else:
                df.to_excel(self.ALL_POSTS_EXCEL_FILE, sheet_name='Posts', index=False)
            print(f"Metadata appended to: {self.ALL_POSTS_EXCEL_FILE}")
        except Exception as e:
            print(f"Error saving to Excel file {self.ALL_POSTS_EXCEL_FILE}: {e}")

    def load_all_posts_data(self):
        """Loads all historical post data from the JSON file."""
        if os.path.exists(self.ALL_POSTS_JSON_FILE):
            try:
                with open(self.ALL_POSTS_JSON_FILE, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    if isinstance(data, list):
                        return data
                    else:
                        print(f"Warning: {self.ALL_POSTS_JSON_FILE} content is not a list. Returning empty list.")
                        return []
            except json.JSONDecodeError:
                print(f"Warning: {self.ALL_POSTS_JSON_FILE} is corrupted. Returning empty list.")
                return []
            except Exception as e:
                print(f"Error loading all posts data from {self.ALL_POSTS_JSON_FILE}: {e}. Returning empty list.")
                return []
        print(f"No existing posts data file found at {self.ALL_POSTS_JSON_FILE}. Returning empty list.")
        return []

# --- Analysis Functions ---

def _load_analysis_results(file_path):
    """Loads previous analysis results from a given file path."""
    if os.path.exists(file_path):
        try:
            with open(file_path, 'r') as f:
                analysis = json.load(f)
            print(f"Loaded analysis from {file_path}")
            return analysis
        except json.JSONDecodeError:
            print(f"Analysis file {file_path} is corrupted. Returning empty data.")
            return {}
        except Exception as e:
            print(f"Error loading analysis from {file_path}: {e}. Returning empty data.")
            return {}
    print(f"No existing analysis file found at {file_path}. Returning empty data.")
    return {}

def _save_analysis_results(analysis_data, file_path):
    """Saves the current analysis results to a given file path."""
    os.makedirs(os.path.dirname(file_path), exist_ok=True)
    try:
        with open(file_path, 'w', encoding='utf-8') as f:
            json.dump(analysis_data, f, indent=4)
        print(f"Saved analysis to {file_path}")
    except Exception as e:
        print(f"Error saving analysis to {file_path}: {e}")

def perform_weekly_analysis(ai_client_for_analysis, local_saver_instance):
    """
    Analyzes past week's content using Deepseek R1 model and generates style recommendations for OWN content.
    """
    print("\n--- Performing Weekly Internal Content Style Analysis ---")

    all_posts_data = local_saver_instance.load_all_posts_data()

    one_week_ago = datetime.now(UTC) - timedelta(days=WEEKLY_ANALYSIS_INTERVAL_DAYS)

    past_week_posts = []
    for post in all_posts_data:
        try:
            # Filter out motivational quote posts from news analysis
            if post.get('Source_Type') == 'motivational_quote_post':
                continue

            if 'Timestamp' in post and isinstance(post['Timestamp'], str):
                post_timestamp = datetime.fromisoformat(post['Timestamp']).replace(tzinfo=UTC)
                if post_timestamp >= one_week_ago:
                    past_week_posts.append({
                        "post_id": post.get('Post_ID', 'N/A'),
                        "timestamp": post['Timestamp'],
                        "content_type": post.get('Source_Type', 'N/A'),
                        "storytelling_method": post.get('Storytelling_Method', 'N/A'),
                        "caption": post.get('SEO_Caption', 'N/A'),
                        "hashtags": post.get('Hashtags', 'N/A')
                    })
            else:
                print(f"Warning: Post data missing valid 'Timestamp' or is not string: {post}. Skipping post for analysis.")
                continue
        except KeyError as e:
            print(f"Warning: Post data missing key for analysis: {e}. Skipping post.")
            continue
        except ValueError as e:
            print(f"Warning: Could not parse timestamp for post: {e}. Skipping post.")
            continue

    if not past_week_posts:
        print("No news posts found from the last week for internal content style analysis. Returning empty recommendations.")
        return {}

    past_content_summary = ""
    for i, post in enumerate(past_week_posts):
        past_content_summary += (
            f"Post {i+1} (ID: {post['post_id']}):\n"
            f"  Type: {post['content_type']}\n"
            f"  Storytelling Method: {post['storytelling_method']}\n"
            f"  Caption: {post['caption']}\n"
            f"  Hashtags: {post['hashtags']}\n"
            "--------------------\n"
        )

    system_message = f"""
    You are an expert social media content strategist specializing in analyzing content performance and providing actionable, creative recommendations for Instagram.
    Your task is to review the provided past news content generated by our system, focusing on Startup, Business, Financial, and Entrepreneurial news.
    Analyze the effectiveness of the chosen storytelling methods, caption styles, and hashtag usage.
    Focus on enhancing reach and engagement. Be specific and provide clear, creative examples for each recommendation.
    Consider how to make the content more useful and complete for the audience, especially for non-open-ended storytelling.
    """
    prompt = f"""Analyze the following past week's generated Instagram content data from our system. For each post, the 'Storytelling Method' used is provided.
    Based on this data, provide specific and actionable recommendations to improve:
    1.  **Overall Content Style and Themes:** What news topics or angles seem most engaging for our target audience (Startup, Business, Financial, Entrepreneurial)? How can the overall aesthetic (colors, fonts, image placement) be refined for a more professional and engaging look?
    2.  **Storytelling Methods:** Which of the used storytelling methods (The Burning Question, The Unexpected Twist, The Ripple Effect, The Human Element, The Hypothetical Future, The Myth Buster, The Origin Story, The Unveiling Mystery) seem to resonate most effectively, or how can they be improved? Provide guidance on when to use each method to achieve desired engagement (e.g., curiosity, discussion, sharing).
    3.  **Caption Style:** How can captions be more impactful, more aligned with the storytelling method, and encourage comments or shares?
    4.  **Hashtag Strategy:** How can hashtag usage be optimized for better discoverability within Startup, Business, Financial, and Entrepreneurial niches?
    5.  **Content Completeness:** For content that is not explicitly open-ended, how can we ensure the summary and caption provide maximum value and completeness to the reader?

    Assume a hypothetical 'performance' where some posts generated more hypothetical comments and shares than others. Your goal is to infer what might lead to higher engagement.

    Past Week's Content Data:
    ---
    {past_content_summary}
    ---

    Provide your analysis and recommendations in a clear, structured format.
    """

    print("Sending past content data to Deepseek R1 for weekly analysis...")
    try:
        response = ai_client_for_analysis.chat.completions.create(
            model=OPENROUTER_DEEPSEEK_R1_MODEL,
            messages=[{"role": "system", "content": system_message}, {"role": "user", "content": prompt}],
            max_tokens=1500,
            temperature=0.7,
            extra_headers={"HTTP-Referer": OPENROUTER_SITE_URL, "X-Site-Name": OPENROUTER_SITE_NAME},
        )
        recommendations_text = response.choices[0].message.content.strip()

        if recommendations_text:
            print("Deepseek R1 Weekly Analysis Result:\n", recommendations_text)
            new_recommendations = {"weekly_analysis": recommendations_text, "timestamp": datetime.now(UTC).isoformat()}
            _save_analysis_results(new_recommendations, STYLE_RECOMMENDATIONS_FILE)
            return new_recommendations
        else:
            print("Failed to get style recommendations from Deepseek R1 (empty response).")
            return {}
    except Exception as e:
        print(f"Error calling Deepseek R1 for weekly analysis: {e}")
        return {}


def perform_internal_instagram_performance_analysis(ai_client_for_analysis, instagram_poster_instance):
    """
    Fetches recent Instagram post insights for *your own* business account via Graph API
    and uses Deepseek R1 to analyze performance based on captions and storytelling methods.
    """
    print("\n--- Performing Internal Instagram Post Performance Analysis ---")

    # DUMMY DATA for demonstration purposes if live API fetching is not set up
    live_insta_posts_data = [
        {"id": "INSTAPOST123", "caption": "The Burning Question: Can this new AI tool really predict market shifts? Insights inside! #AIinFinance #MarketPredictions", "media_type": "IMAGE", "likes": 500, "comments": 80, "shares": 20, "saves": 30, "storytelling_method": "The Burning Question", "source_type": "startup_news", "timestamp": (datetime.now(UTC) - timedelta(days=1)).isoformat()},
        {"id": "INSTAPOST124", "caption": "The Unexpected Twist: This business model was doomed... until it wasn't. Learn their secret! #BusinessSuccess #Innovation", "media_type": "IMAGE", "likes": 300, "comments": 40, "shares": 10, "saves": 15, "storytelling_method": "The Unexpected Twist", "source_type": "business_news", "timestamp": (datetime.now(UTC) - timedelta(hours=30)).isoformat()},
        {"id": "INSTAPOST125", "caption": "The Ripple Effect: How one small startup's funding round is changing the entire investment landscape. #StartupFunding #Fintech", "media_type": "IMAGE", "likes": 600, "comments": 100, "shares": 25, "saves": 40, "storytelling_method": "The Ripple Effect", "source_type": "financial_news", "timestamp": (datetime.now(UTC) - timedelta(days=2)).isoformat()},
        {"id": "INSTAPOST126", "caption": "The Human Element: Meet the founder who built an empire from a single idea and a shoestring budget. #EntrepreneurLife #Inspiration", "media_type": "IMAGE", "likes": 450, "comments": 60, "shares": 15, "saves": 25, "storytelling_method": "The Human Element", "source_type": "entrepreneurial_news", "timestamp": (datetime.now(UTC) - timedelta(hours=50)).isoformat()},
        # Dummy data for motivational quote post
        {"id": "INSTAPOST127", "caption": "Believe you can and you're halfway there. ✨ What's stopping you from starting today? #Motivation #DailyQuote #EntrepreneurMindset", "media_type": "IMAGE", "likes": 700, "comments": 120, "shares": 50, "saves": 80, "storytelling_method": "N/A", "source_type": "motivational_quote_post", "timestamp": (datetime.now(UTC) - timedelta(days=1)).isoformat()},
    ]
    # Filter for posts within the analysis interval
    filtered_insta_posts = []
    time_threshold = datetime.now(UTC) - timedelta(days=INSTAGRAM_ANALYSIS_INTERVAL_DAYS)
    for post in live_insta_posts_data:
        if 'timestamp' in post and datetime.fromisoformat(post['timestamp']).replace(tzinfo=UTC) >= time_threshold:
            filtered_insta_posts.append(post)

    if not filtered_insta_posts:
        print("No recent Instagram posts found from your account for internal analysis. Skipping.")
        _save_analysis_results({"last_run": datetime.now(UTC).isoformat(), "analysis_result": "No posts to analyze."}, INSTAGRAM_ANALYSIS_FILE)
        return

    analysis_data_for_ai = []
    for post in filtered_insta_posts:
        engagement_score = post.get('likes', 0) + post.get('comments', 0) + post.get('shares', 0) + post.get('saves', 0)
        analysis_data_for_ai.append(
            f"Post ID: {post['id']}\n"
            f"  Content Type: {post['source_type']}\n" # Added content type
            f"  Storytelling Method: {post['storytelling_method']}\n"
            f"  Caption: {post['caption']}\n"
            f"  Engagement Score (Likes+Comments+Shares+Saves): {engagement_score}\n"
            f"  Likes: {post['likes']}, Comments: {post['comments']}, Shares: {post['shares']}, Saves: {post['saves']}\n"
            f"--------------------\n"
        )

    system_message = f"""
    You are an expert social media performance analyst. Your task is to analyze the provided data from OUR OWN Instagram Business Account's recent posts.
    Identify patterns of high and low performance related to:
    1.  **Storytelling Method Effectiveness:** Which specific storytelling methods (e.g., 'The Burning Question', 'The Ripple Effect') seem to lead to higher engagement metrics (likes, comments, shares, saves)? Provide insights into *why* they might be working.
    2.  **Caption Effectiveness:** What elements in captions (e.g., call-to-actions, tone, length, clarity, use of emojis/questions) correlate with better performance?
    3.  **Overall Post Strategy:** Suggest concrete, actionable improvements for our future Instagram posts to maximize engagement based on actual past performance.
    4.  **Content Completeness vs. Open-Ended:** Analyze if posts intended to be 'complete' achieved that, and if 'open-ended' ones successfully drove discussion.
    5.  **Motivational Quote Post Performance:** Specifically analyze how the dedicated motivational quote posts perform compared to news posts. What makes them effective or what can be improved in their captioning and hashtag strategy?
    """

    prompt = f"""Analyze the following performance data from our Instagram posts. Each entry includes the Post ID, the Content Type (news vs. motivational_quote_post), the Storytelling Method used (if applicable), the Caption, and various engagement metrics (Likes, Comments, Shares, Saves).
    Based on this analysis:
    -   **Performance by Content Type:** How do motivational quote posts perform compared to news posts in terms of overall engagement?
    -   **Storytelling Method Performance (for News Posts):** Which news storytelling methods appear to be the most effective for *our* audience (Startup, Business, Financial, Entrepreneurial niches), and why? Discuss how different methods encourage different types of engagement.
    -   **Caption Characteristics for Success:** Detail the common characteristics of captions from high-performing posts across *all* content types. What makes them engaging for our target audience?
    -   **User Interaction Insights (Comments & Shares):** What kind of comments and shares (if data available) do high-performing posts tend to attract? What does this tell us about what truly resonates?
    -   **Actionable Recommendations:** Provide 3-5 specific, actionable recommendations for improving our next batch of Instagram posts to boost overall engagement (likes, comments, shares, saves), considering the effectiveness of storytelling, captioning, and content completeness for both news and motivational quote formats.

    Here is the data:
    ---
    {"".join(analysis_data_for_ai)}
    ---

    Provide your analysis and recommendations in a clear, structured format.
    """

    print("Sending internal Instagram post data to Deepseek R1 for performance analysis...")
    try:
        response = ai_client_for_analysis.chat.completions.create(
            model=OPENROUTER_DEEPSEEK_R1_MODEL,
            messages=[{"role": "system", "content": system_message}, {"role": "user", "content": prompt}],
            max_tokens=1500,
            temperature=0.7,
            extra_headers={"HTTP-Referer": OPENROUTER_SITE_URL, "X-Site-Name": OPENROUTER_SITE_NAME},
        )
        analysis_result_text = response.choices[0].message.content.strip()

        if analysis_result_text:
            print("Deepseek R1 Internal Instagram Analysis Result:\n", analysis_result_text)
            new_analysis_data = {"last_run": datetime.now(UTC).isoformat(), "analysis_result": analysis_result_text}
            _save_analysis_results(new_analysis_data, INSTAGRAM_ANALYSIS_FILE)
        else:
            print("Failed to get internal Instagram analysis from Deepseek R1 (empty response).")
            new_analysis_data = {"last_run": datetime.now(UTC).isoformat(), "analysis_result": "Empty response from AI."}
            _save_analysis_results(new_analysis_data, INSTAGRAM_ANALYSIS_FILE)
    except Exception as e:
        print(f"Error calling Deepseek R1 for internal Instagram analysis: {e}")
        new_analysis_data = {"last_run": datetime.now(UTC).isoformat(), "analysis_result": f"API error: {e}"}
        _save_analysis_results(new_analysis_data, INSTAGRAM_ANALYSIS_FILE)


def perform_external_instagram_analysis(ai_client_for_analysis):
    """
    (CONCEPTUAL ONLY - HIGHLY LIMITED / NOT LIVE)
    This function simulates analyzing other Instagram content.
    Actual implementation for this is NOT possible via public Instagram Graph API for general search.
    This function will use DUMMY/SIMULATED data to demonstrate the analytical *logic*.
    """
    print("\n--- Performing Conceptual External Instagram Content Analysis ---")

    # SIMULATED EXTERNAL DATA: Represents data *you would hypothetically gather* from other successful posts/accounts.
    simulated_external_posts = [
        {"caption": "The future of AI in finance is here, but are you ready for the disruption? 🔥 #Fintech #AI #Disruptor", "comments_count": 250, "likes_count": 5000, "content_theme": "AI in Finance News", "account_handle": "@FintechFuture"},
        {"caption": "Unlocking the secrets of venture capital: What VCs *really* look for in a startup pitch. 👀 #VCRules #StartupFunding", "comments_count": 180, "likes_count": 3500, "content_theme": "Venture Capital News", "account_handle": "@StartupInsights"},
        {"caption": "This small business turned a local idea into a global sensation! Their growth hacks are insane. 🚀 #SmallBiz #GrowthHacks", "comments_count": 300, "likes_count": 6000, "content_theme": "Small Business Growth News", "account_handle": "@GlobalBizTips"},
        {"caption": "Don't fall for these common investment myths! A deep dive into what truly builds wealth. 💰 #InvestingTips #WealthBuilding", "comments_count": 120, "likes_count": 2800, "content_theme": "Investment Myths News", "account_handle": "@SmartInvestor"},
        {"caption": "The one mindset shift every aspiring entrepreneur needs to make TODAY. This will change everything. ✨ #EntrepreneurMindset #Success", "comments_count": 400, "likes_count": 7500, "content_theme": "Entrepreneurial Mindset Quote", "account_handle": "@InspireEntrepreneurs"},
        {"caption": "Is the tech bubble about to burst, or is this just the calm before the storm? Experts weigh in. 📉📈 #TechBubble #MarketAnalysis", "comments_count": 150, "likes_count": 3000, "content_theme": "Market Trends News", "account_handle": "@MarketWatchers"},
        # Added a simulated external quote post
        {"caption": "Your potential is endless. Go do what you were created to do! #Motivation #UnleashYourPotential #SuccessMindset", "comments_count": 500, "likes_count": 8000, "content_theme": "Inspirational Quote", "account_handle": "@DailyMotivator"},
    ]

    if not simulated_external_posts:
        print("No simulated external Instagram posts found for analysis. Skipping.")
        _save_analysis_results({"last_run": datetime.now(UTC).isoformat(), "analysis_result": "No simulated external posts to analyze."}, EXTERNAL_INSTAGRAM_ANALYSIS_FILE)
        return

    analysis_data_for_ai = []
    for i, post in enumerate(simulated_external_posts):
        analysis_data_for_ai.append(
            f"External Post {i+1} (Account: {post['account_handle']}):\n"
            f"  Caption: {post['caption']}\n"
            f"  Likes: {post['likes_count']}, Comments: {post['comments_count']}\n"
            f"  Content Theme: {post['content_theme']}\n"
            f"--------------------\n"
        )

    system_message = f"""
    You are a highly analytical social media expert. Your task is to analyze provided sample data from *other* successful Instagram posts (captions, likes, comments, themes).
    Your goal is to identify patterns and best practices that contribute to high engagement and effective content strategies for Startup, Business, Financial, and Entrepreneurial niches.
    Focus on understanding:
    1.  **What kind of post is performing better?** (e.g., content themes, topics, types of news, visual style inferred from description, motivational vs news)
    2.  **Why is it performing better?** (e.g., specific caption elements, call-to-actions, tone, emotional appeal, storytelling style implicitly used, relevance)
    3.  **Analyze with captions:** How are captions structured? What kind of language is used? How do they encourage interaction?
    4.  **Comment Analysis:** What kind of comments do these posts attract? (e.g., questions, debates, personal stories, requests for more info, positive feedback)
    Provide actionable insights for *our* content creation.
    """

    prompt = f"""Analyze the following simulated data from other Instagram posts. Each entry includes a caption, likes, comments, and a content theme (e.g., "AI in Finance News", "Inspirational Quote").
    Based on this data, provide a comprehensive analysis:
    -   **Performance by Content Type:** How do dedicated inspirational/motivational quote posts perform compared to news-focused posts on other successful accounts?
    -   **High-Performing Content Themes/Types:** Which specific themes or types of posts (e.g., "AI in Finance News", "Small Business Growth News", "Inspirational Quote") seem to get the most engagement, and why?
    -   **Caption Effectiveness:** Break down the characteristics of captions from high-performing posts, differentiating between news and quote posts if applicable. What makes them engaging? (e.g., use of strong hooks, questions, emojis, calls to action, emotional connection, concise messaging)
    -   **Audience Interaction (Comments):** Describe the nature and sentiment of comments on the top-performing posts. What are users saying, and what does this tell us about what truly resonates?
    -   **General Strategic Takeaways:** What overarching lessons can we learn from these examples to apply to our own Startup, Business, Financial, and Entrepreneurial content on Instagram? Suggest ways to integrate their successful strategies with our unique storytelling methods and distinct motivational quote format.

    Here is the simulated data:
    ---
    {"".join(analysis_data_for_ai)}
    ---

    Provide your analysis and recommendations in a clear, structured, and actionable format.
    """
    print("Sending conceptual external Instagram post data to Deepseek R1 for analysis...")
    try:
        response = ai_client_for_analysis.chat.completions.create(
            model=OPENROUTER_DEEPSEEK_R1_MODEL,
            messages=[{"role": "system", "content": system_message}, {"role": "user", "content": prompt}],
            max_tokens=1500,
            temperature=0.7,
            extra_headers={"HTTP-Referer": OPENROUTER_SITE_URL, "X-Site-Name": OPENROUTER_SITE_NAME},
        )
        analysis_result_text = response.choices[0].message.content.strip()

        if analysis_result_text:
            print("Deepseek R1 Conceptual External Instagram Analysis Result:\n", analysis_result_text)
            new_analysis_data = {"last_run": datetime.now(UTC).isoformat(), "analysis_result": analysis_result_text}
            _save_analysis_results(new_analysis_data, EXTERNAL_INSTAGRAM_ANALYSIS_FILE)
        else:
            print("Failed to get conceptual external Instagram analysis from Deepseek R1 (empty response).")
            new_analysis_data = {"last_run": datetime.now(UTC).isoformat(), "analysis_result": "Empty response from AI."}
            _save_analysis_results(new_analysis_data, EXTERNAL_INSTAGRAM_ANALYSIS_FILE)
    except Exception as e:
        print(f"Error calling Deepseek R1 for conceptual external analysis: {e}")
        new_analysis_data = {"last_run": datetime.now(UTC).isoformat(), "analysis_result": f"API error: {e}"}
        _save_analysis_results(new_analysis_data, EXTERNAL_INSTAGRAM_ANALYSIS_FILE)


def check_api_keys():
    """Checks if essential API keys are placeholder strings. Provides warnings."""
    warnings = []
    if OPENROUTER_API_KEY == "sk-or-v1-YOUR_DEEPSEEK_CHAT_API_KEY_HERE":
        warnings.append("OPENROUTER_API_KEY (for Deepseek Chat) is still a placeholder. AI text processing might be limited or fail.")
    if OPENROUTER_DEEPSEEK_R1_API_KEY == "sk-or-v1-YOUR_DEEPSEEK_R1_API_KEY_HERE":
        warnings.append("OPENROUTER_DEEPSEEK_R1_API_KEY (for Deepseek R1 analysis) is still a placeholder. Analysis tasks might fail.")
    if OPENROUTER_MISTRAL_API_KEY == "sk-or-v1-YOUR_MISTRAL_SMALL_API_KEY_HERE":
        warnings.append("OPENROUTER_MISTRAL_API_KEY (for Mistral) is still a placeholder. Caption/hashtag generation might fail.")
    if PEXELS_API_KEY == "YOUR_PEXELS_API_KEY_HERE":
        warnings.append("PEXELS_API_KEY is still a placeholder. Pexels image fetches might be limited or fail.")
    if UNSPLASH_ACCESS_KEY == "YOUR_UNSPLASH_ACCESS_KEY_HERE":
        warnings.append("UNSPLASH_ACCESS_KEY is still a placeholder. Unsplash image fetches might be limited or fail.")
    if PIXABAY_API_KEY == "YOUR_PIXABAY_API_KEY_HERE":
        warnings.append("PIXABAY_API_KEY is still a placeholder. Pixabay image fetches might be limited or fail.")
    if CLOUDINARY_CLOUD_NAME == "YOUR_CLOUDINARY_CLOUD_NAME_HERE" or \
       CLOUDINARY_API_KEY == "YOUR_CLOUDINARY_API_KEY_HERE" or \
       CLOUDINARY_API_SECRET == "YOUR_CLOUDINARY_API_SECRET_HERE":
        warnings.append("Cloudinary API credentials are still placeholders. Image upload will fail.")
    if FB_PAGE_ACCESS_TOKEN == "YOUR_FB_PAGE_ACCESS_TOKEN_HERE" or \
       INSTAGRAM_BUSINESS_ACCOUNT_ID == "YOUR_INSTAGRAM_BUSINESS_ACCOUNT_ID_HERE":
        warnings.append("Instagram Graph API credentials are still placeholders. Instagram posting will fail.")
    if not os.path.exists("fonts/AlfaSlabOne-Regular.ttf"):
        warnings.append("Font file 'AlfaSlabOne-Regular.ttf' not found in 'fonts/' directory. Using fallback font.")
    if not os.path.exists("fonts/Tapestry-Regular.ttf"):
        warnings.append("Font file 'Tapestry-Regular.ttf' not found in 'fonts/' directory. Using fallback font.")

    if warnings:
        print("\n--- API KEY / CONFIGURATION WARNINGS ---")
        for warning in warnings:
            print(f"- {warning}")
        print("----------------------------------------\n")

# --- Main Workflow Execution ---
def run_workflow(): # Wrapped main logic in a function
    # Moved object instantiation inside run_workflow
    workflow_manager = WorkflowStateManager()
    news_fetcher = NewsFetcher()
    text_processor = TextProcessor()
    image_fetcher = ImageFetcher()
    image_local_processor = ImageLocalProcessor()
    caption_generator = CaptionGenerator()
    cloudinary_uploader = CloudinaryUploader()
    instagram_poster = InstagramPoster()
    local_saver = LocalSaver(IMAGE_OUTPUT_DIR, JSON_OUTPUT_DIR, EXCEL_OUTPUT_DIR, ALL_POSTS_JSON_FILE, ALL_POSTS_EXCEL_FILE)

    ai_client_for_analysis = OpenAI(
        base_url="https://openrouter.ai/api/v1",
        api_key=OPENROUTER_DEEPSEEK_R1_API_KEY, # This should be correct now
    )

    # All these operations were already wrapped in try-except in run_workflow()
    # The crucial fix is how `local_saver.save_post` gets `workflow_manager`
    # And ensuring consistent returns/exits.

    # Internal Content Style Analysis (weekly)
    current_style_recommendations = _load_analysis_results(STYLE_RECOMMENDATIONS_FILE)
    recommendation_text_for_llm = current_style_recommendations.get('weekly_analysis', '')

    if workflow_manager.should_run_weekly_analysis():
        print("Time to run weekly content style analysis...")
        try:
            new_recommendations = perform_weekly_analysis(ai_client_for_analysis, local_saver)
            if new_recommendations:
                current_style_recommendations = new_recommendations
                recommendation_text_for_llm = current_style_recommendations.get('weekly_analysis', '')
            workflow_manager.update_last_analysis_timestamp()
        except Exception as e:
            print(f"Error during weekly content style analysis: {e}")
            import traceback
            traceback.print_exc()

    # Internal Instagram Post Performance Analysis (every 3 days)
    if workflow_manager.should_run_instagram_analysis():
        print("Time to run internal Instagram post performance analysis...")
        try:
            perform_internal_instagram_performance_analysis(ai_client_for_analysis, instagram_poster)
            workflow_manager.update_last_instagram_analysis_timestamp()
        except Exception as e:
            print(f"Error during internal Instagram performance analysis: {e}")
            import traceback
            traceback.print_exc()

    # Conceptual External Instagram Content Analysis (weekly)
    if workflow_manager.should_run_external_instagram_analysis():
        print("Time to run conceptual external Instagram content analysis...")
        try:
            perform_external_instagram_analysis(ai_client_for_analysis)
            workflow_manager.update_last_external_instagram_analysis_timestamp()
        except Exception as e:
            print(f"Error during conceptual external Instagram analysis: {e}")
            import traceback
            traceback.print_exc()


    if recommendation_text_for_llm:
        print(f"\nApplying current style recommendations:\n{recommendation_text_for_llm}\n")
    else:
        print("\nNo specific style recommendations to apply at this time.\n")


    content_type_for_this_run = workflow_manager.get_current_post_type()
    post_number_for_this_run = workflow_manager.get_current_post_number()

    print(f"\n--- Processing Post {post_number_for_this_run}/{len(CONTENT_TYPE_CYCLE)} (Type: {content_type_for_this_run.replace('_', ' ').title()}) ---")

    post_to_process = {'type': content_type_for_this_run, 'content_type_display': content_type_for_this_run} # Initialize for all post types
    fetched_pil_image = None # Initialize fetched_pil_image outside the if/else

    # NEW: Function to generate motivational quote using AI
    def generate_motivational_quote_with_ai(content_hint: str, ai_client_instance: OpenAI, api_key: str, site_url: str, site_name: str):
        """Generates a motivational quote and author using AI."""
        if api_key == "sk-or-v1-YOUR_OPENROUTER_DEEPSEEK_API_KEY": # Use the correct placeholder check
            print("OPENROUTER_API_KEY for Deepseek Chat is a placeholder. Skipping AI quote generation.")
            return {"quote": "The only way to do great work is to love what you do.", "author": "Steve Jobs (Fallback)"}

        system_message = f"""
        You are a creative AI assistant specializing in generating concise and impactful motivational quotes for social media.
        Your task is to create an original motivational quote and attribute it to a relevant, inspiring figure (real or conceptual, e.g., "A Visionary", "The Innovator", "Anonymous").
        The quote should be highly relevant to the theme of {content_hint.replace('_', ' ').title()}.
        The quote should be short, impactful, and easily digestible for an Instagram post. Aim for 15-25 words.
        Return ONLY a JSON object with two keys: "quote" (string) and "author" (string).
        """
        user_message = f"""
        Generate a motivational quote and author related to {content_hint.replace('_', ' ').title()}.
        Example: {{"quote": "The future belongs to those who believe in the beauty of their dreams.", "author": "Eleanor Roosevelt"}}
        """
        messages = [
            {"role": "system", "content": system_message},
            {"role": "user", "content": user_message}
        ]

        try:
            completion = ai_client_instance.chat.completions.create(
                extra_headers={
                    "HTTP-Referer": site_url,
                    "X-Title": site_name,
                },
                model=OPENROUTER_MODEL, # Use the general OPENROUTER_MODEL for content generation
                messages=messages,
                temperature=0.9, # Higher temperature for creativity
                max_tokens=100, # Keep response concise
                response_format={"type": "json_object"}
            )
            if completion.choices and completion.choices[0].message and completion.choices[0].message.content:
                ai_content_str = completion.choices[0].message.content
                try:
                    parsed_data = json.loads(ai_content_str)
                    quote = parsed_data.get('quote', "Innovation is seeing what everybody has seen and thinking what nobody else has thought.")
                    author = parsed_data.get('author', "An Innovator")
                    # Basic word count check for quotes
                    if len(quote.split()) > 30: # Limit generated quote length
                        quote = ' '.join(quote.split()[:30]) + "..."
                    return {"quote": quote, "author": author}
                except json.JSONDecodeError:
                    print(f"Warning: AI did not return valid JSON for quote. Raw: {ai_content_str[:100]}...")
                    return {"quote": "The only way to do great work is to love what you do.", "author": "Steve Jobs (Fallback)"}
            return {"quote": "The only way to do great work is to love what you do.", "author": "Steve Jobs (Fallback)"}
        except Exception as e:
            print(f"Error generating quote with AI: {e}")
            return {"quote": "The only way to do great work is to love what you do.", "author": "Steve Jobs (API Error)"}


    if content_type_for_this_run == 'motivational_quote_post':
        print("Generating a Motivational Quote Post...")
        # Use AI to generate the quote
        # Pass the content type as a hint for the AI
        quote_content_hint = random.choice(['startup', 'business', 'financial', 'entrepreneurial', 'technology'])
        generated_quote_data = generate_motivational_quote_with_ai(
            content_hint=quote_content_hint,
            ai_client_instance=text_processor.client, # Reuse text_processor's client for Deepseek Chat
            api_key=OPENROUTER_API_KEY,
            site_url=OPENROUTER_SITE_URL,
            site_name=OPENROUTER_SITE_NAME
        )
        post_to_process['quote_text'] = generated_quote_data['quote']
        post_to_process['quote_author'] = generated_quote_data['author']
        post_to_process['title'] = generated_quote_data['quote'] # Use quote as title for consistency in metadata
        post_to_process['summary'] = generated_quote_data['author'] # Use author as summary for consistency in metadata
        post_to_process['storytelling_method'] = 'Motivational Quote'
        # For quote posts, the 'image' is just a placeholder to pass to the processor, which then draws the background
        fetched_pil_image = Image.new('RGB', (CANVAS_WIDTH, IMAGE_DISPLAY_HEIGHT), color=(251, 234, 231))
        post_to_process['image_status'] = 'generated_placeholder'

    else: # It's a news post (startup, business, financial, entrepreneurial)
        news_item = news_fetcher.get_single_content_item(content_type_for_this_run)

        if not news_item:
            print(f"No recent news available for '{content_type_for_this_run.replace('_', ' ').title()}' after all attempts. Skipping post creation for this cycle.")
            workflow_manager.increment_post_type_index()
            return # Use return False to signal failure, not sys.exit(0)

        post_to_process.update(news_item) # Add news item data to post_to_process
        post_to_process['original_description'] = post_to_process.get('description', 'N/A')

        print(f"Original Title: {post_to_process.get('title', 'N/A')}")
        print(f"Original Description: {post_to_process.get('description', 'N/A')[:100]}...")

        # 1. Summarize and Enhance Text (OpenRouter - Deepseek) with Storytelling
        short_title, summary, storytelling_method_used, text_process_success = text_processor.process_text(
            post_to_process.get('title', ''),
            post_to_process.get('description', ''),
            post_to_process.get('type', ''),
            style_recommendations=recommendation_text_for_llm
        )

        if not text_process_success:
            print(f"Deepseek text processing failed for this post. Skipping post creation for this cycle.")
            workflow_manager.increment_post_type_index()
            return # Use return False to signal failure

        post_to_process['title'] = short_title
        post_to_process['summary'] = summary
        post_to_process['storytelling_method'] = storytelling_method_used
        post_to_process['seo_caption'] = ""
        post_to_process['hashtags'] = []

        print(f"Generated Short Title (Storytelling: {storytelling_method_used}): {short_title}")
        print(f"Generated Summary: {summary}")

        # 2. Fetch Relevant Image for News Post
        image_search_prompt = f"{short_title} {summary} {content_type_for_this_run.replace('_', '')}" # Removed space in replace for consistency
        print(f"Fetching image for: {image_search_prompt[:80]}...")
        fetched_pil_image = image_fetcher.fetch_image(image_search_prompt)

        if fetched_pil_image is None:
            print(f"No relevant image found from any source for prompt: {image_search_prompt}. Generating placeholder image.")
            fetched_pil_image = Image.new('RGB', (CANVAS_WIDTH, IMAGE_DISPLAY_HEIGHT), color=(70, 70, 70))
            draw_placeholder = ImageDraw.Draw(fetched_pil_image)
            fallback_font = load_font(FONT_PATH_ALFA_SLAB_ONE, 50)
            text_to_draw = "IMAGE NOT AVAILABLE"
            text_bbox = draw_placeholder.textbbox((0,0), text_to_draw, font=fallback_font)
            text_width = text_bbox[2] - text_bbox[0]
            text_height = text_bbox[3] - text_bbox[1]
            draw_placeholder.text(((CANVAS_WIDTH - text_width) / 2, (IMAGE_DISPLAY_HEIGHT - text_height) / 2),
                                  text_to_draw, font=fallback_font, fill=COLOR_SOURCE_TEXT)
            post_to_process['image_status'] = 'placeholder'
        else:
            post_to_process['image_status'] = 'fetched'


    # 3. Overlay Text on Image and Compose Final Post
    print("Composing final post image with overlays...")
    final_post_image = image_local_processor.overlay_text(fetched_pil_image, {
        'title': post_to_process.get('title', ''), # For news, this is short_title; for quotes, this is quote_text
        'summary': post_to_process.get('summary', ''), # For news, this is summary; for quotes, this is author
        'timestamp': datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        'source': post_to_process.get('source', 'Unknown Source') if 'source' in post_to_process else 'N/A', # Add check for 'source' key
        'content_type_display': post_to_process.get('type')
    })
    post_to_process['final_image'] = final_post_image

    # 4. Generate Caption + Hashtags (Mistral via OpenRouter)
    print("Generating caption and hashtags with Mistral...")
    instagram_caption, instagram_hashtags, caption_success = caption_generator.generate_caption_and_hashtags(
        post_to_process['title'], # For news, this is short_title; for quotes, this is quote_text
        post_to_process['summary'], # For news, this is summary; for quotes, this is author
        post_to_process.get('storytelling_method', 'N/A'),
        post_to_process['type'], # Pass post_type to caption generator for custom prompts
        style_recommendations=recommendation_text_for_llm
    )

    post_to_process['seo_caption'] = instagram_caption
    post_to_process['hashtags'] = instagram_hashtags

    print(f"Generated Instagram Caption: {instagram_caption[:100]}...")
    print(f"Generated Hashtags: {', '.join(instagram_hashtags)}")

    # 5. Save All Results Locally - Pass workflow_manager_instance here
    print("Saving post metadata and local image...")
    local_saver.save_post(post_to_process, workflow_manager) # Pass workflow_manager here


    # 6. Upload image to Cloudinary
    cloudinary_media_url = None
    media_to_upload_path = os.path.join(IMAGE_OUTPUT_DIR, f"{post_to_process['Post_ID']}.png")
    if post_to_process['final_image'] and os.path.exists(media_to_upload_path):
        print("Uploading image to Cloudinary...")
        cloudinary_media_url = cloudinary_uploader.upload_image(
            media_to_upload_path,
            public_id=post_to_process['Post_ID'],
            folder="insight_pulse_posts"
        )
        post_to_process['cloudinary_url'] = cloudinary_media_url
    else:
        print("Skipping Cloudinary upload: No valid local image found at path or image not generated.")
        post_to_process['cloudinary_url'] = "N/A - Image not uploaded"


    # 7. Post to Instagram
    if cloudinary_media_url:
        print("Attempting to post to Instagram...")
        combined_caption = f"{post_to_process['seo_caption']}\n\n{' '.join(post_to_process['hashtags'])}"
        instagram_post_success = instagram_poster.post_image(cloudinary_media_url, combined_caption)
        post_to_process['instagram_posted'] = instagram_post_success
    else:
        print("Skipping Instagram post: No Cloudinary image URL available.")
        post_to_process['instagram_posted'] = False


    # Final state update and exit
    if 'final_image' in post_to_process:
        del post_to_process['final_image']

    workflow_manager.increment_post_type_index()
    print(f"Successfully processed post {post_number_for_this_run}/{len(CONTENT_TYPE_CYCLE)}. State updated for next trigger.")


if __name__ == "__main__":
    try:
        run_workflow()
    except Exception as e:
        print(f"\nCritical error during workflow execution: {e}")
        print("Exiting application due to critical error.")
        sys.exit(1)