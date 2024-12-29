# Instagram Comment Scraper and Analyzer

This project is an open-source tool designed to scrape and analyze comments from Instagram profiles. It offers multi-language support for comment filtering and sentiment analysis.

## Features

- Scrape comments from multiple Instagram profiles
- Filter comments by language (single or multiple languages)
- Perform sentiment analysis on comments
- Generate separate files for positive comments in different languages
- Create lists of usernames who posted positive comments

## Prerequisites

Before you begin, ensure you have met the following requirements:

- Python 3.7 or higher
- Chrome browser installed
- ChromeDriver compatible with your Chrome version

## Installation

1. Clone the repository:
   ```
   git clone https://github.com/yourusername/instagram-comment-scraper.git
   cd instagram-comment-scraper
   ```

2. Create a virtual environment (recommended):
   ```
   python -m venv venv
   source venv/bin/activate  # On Windows use `venv\Scripts\activate`
   ```

3. Install the required packages:
   ```
   pip install -r requirements.txt
   ```

4. Download ChromeDriver:
   - Visit the [ChromeDriver downloads page](https://sites.google.com/a/chromium.org/chromedriver/downloads)
   - Download the version that matches your Chrome browser
   - Place the `chromedriver` executable in your system PATH or in the project directory

## Configuration

1. Modify the `config.yml` file in the project root directory:
   ```yaml
   username: "your_instagram_username"
   password: "your_instagram_password"
   influencers:
     - profile_url: "https://www.instagram.com/influencer1/"
       num_posts: 10
     - profile_url: "https://www.instagram.com/influencer2/"
       num_posts: -1  # Scrape all available posts
   ```

2. Replace `your_instagram_username` and `your_instagram_password` with your actual Instagram login credentials.
3. Add the Instagram profiles you want to scrape under the `influencers` section.

## Usage

To run the script, use the following command:

```
python scrape_analyze.py
```

Follow the prompts to select your language filtering options:

1. English
2. German
3. English and German
4. Custom selection (multiple languages)

For custom selection, enter the ISO 639-1 language codes separated by commas (e.g., "en,de,fr,es" for English, German, French, and Spanish).

## Output

The script will create a new directory with the current date and time, containing:

- JSON files with scraped comments for each influencer
- A merged JSON file with all comments
- JSON files with comments categorized by sentiment (very negative, negative, neutral, positive)
- JSON files with positive comments for each selected language
- Text files with usernames of users who posted positive comments, for each selected language

## Disclaimer

This tool is for educational purposes only. Be sure to comply with Instagram's terms of service and respect user privacy when using this tool.

## Known Issues

Currently there is no way to scrape reels if they are removed from the feed tab and just visible in the reels tab on a profile.
