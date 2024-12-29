import json
import time
import yaml
import os
import pickle
from collections import defaultdict
from datetime import datetime
from tqdm import tqdm
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.common.exceptions import NoSuchElementException, TimeoutException, StaleElementReferenceException
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from transformers import pipeline
import torch
from langdetect import detect, LangDetectException

def read_config(file_path):
    with open(file_path, 'r') as file:
        return yaml.safe_load(file)

def handle_cookies(driver):
    try:
        WebDriverWait(driver, 10).until(
            EC.element_to_be_clickable((By.XPATH, "//button[contains(text(), 'Allow all cookies')] | //button[contains(text(), 'Alle Cookies erlauben')]"))
        ).click()
        print("Cookies accepted.")
    except TimeoutException:
        print("No cookies button found or not clickable.")

def load_cookies(driver, cookie_file):
    if os.path.exists(cookie_file):
        cookies = pickle.load(open(cookie_file, "rb"))
        for cookie in cookies:
            driver.add_cookie(cookie)
        driver.refresh()
        time.sleep(2)  # Delay after loading cookies
        print("Cookies loaded.")
        return True
    return False

def save_cookies(driver, cookie_file):
    pickle.dump(driver.get_cookies(), open(cookie_file, "wb"))
    print("Cookies saved.")

def instagram_login(driver, username, password, cookie_file):
    driver.get("https://www.instagram.com/")
    time.sleep(2)  # Wait for the initial page to load

    if not load_cookies(driver, cookie_file):
        driver.find_element(By.NAME, 'username').send_keys(username)
        driver.find_element(By.NAME, 'password').send_keys(password)
        driver.find_element(By.NAME, 'password').send_keys(Keys.ENTER)
        time.sleep(5)  # Wait for possible post-login prompts

        handle_cookies(driver)

        # Handling Save Your Login Info
        try:
            WebDriverWait(driver, 10).until(
                EC.element_to_be_clickable((By.XPATH, "//button[contains(text(), 'Save Info')]"))
            ).click()
            print("Login information saved.")
        except TimeoutException:
            print("No prompt to save login information.")

        save_cookies(driver, cookie_file)

def scroll_down(driver, scroll_pause_time=2):
    last_height = driver.execute_script("return document.body.scrollHeight")

    while True:
        print("Scrolling down...")
        driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
        time.sleep(scroll_pause_time)

        new_height = driver.execute_script("return document.body.scrollHeight")
        if new_height == last_height:
            break
        last_height = new_height

def scrape_comments(driver, profile_url, num_posts):
    driver.get(profile_url)
    time.sleep(3)  # Allow the profile page to load completely
    posts = driver.find_elements(By.XPATH, "//a[contains(@href, '/p/')]")
    if num_posts != -1:
        posts = posts[:num_posts]

    results = {}
    print(f"Found {len(posts)} posts, processing the latest {num_posts}.")

    for i, post in enumerate(posts):
        print(f"\nProcessing post {i + 1}/{num_posts}")
        post.click()
        time.sleep(3)  # Allow the post to load completely

        load_more_count = 0
        while True:
            print("Attempting to load more comments...")
            try:
                # Look for the "Load more comments" button
                load_more_button = WebDriverWait(driver, 5).until(
                    EC.element_to_be_clickable((By.XPATH, "//button//*[contains(text(), 'Load more comments') or contains(text(), 'View more comments')]/.."))
                )
                # Click the "Load more comments" button
                print("Found 'Load more comments' button, clicking it.")
                load_more_button.click()
                load_more_count += 1
                print(f"Clicked 'Load more comments' button {load_more_count} times.")
                time.sleep(2)
            except TimeoutException:
                print(f"No more 'Load more comments' button found. Clicked {load_more_count} times.")
                break

            # Scroll down to load more comments
            scroll_down(driver)

        print("Finished loading comments. Now collecting comment data...")

        # Collect comments
        comment_elements = driver.find_elements(By.XPATH, "//ul[contains(@class, '_a9ym')]//li[contains(@class, '_a9zj')]")

        for comment in comment_elements:
            try:
                username_element = comment.find_element(By.XPATH, ".//h3[contains(@class, '_a9zc')]//a")
                username = username_element.text
                comment_text_element = comment.find_element(By.XPATH, ".//div[contains(@class, '_a9zs')]//span")
                comment_text = comment_text_element.text

                if username and comment_text:
                    if username not in results:
                        results[username] = []
                    results[username].append(comment_text)
                    print(f"Added comment by {username}: '{comment_text}'")
            except (NoSuchElementException, StaleElementReferenceException) as e:
                print(f"Error collecting comment data: {e}")
                continue

        # Close the post
        try:
            close_button = WebDriverWait(driver, 10).until(
                EC.element_to_be_clickable((By.XPATH, "//div[@class='x160vmok x10l6tqk x1eu8d0j x1vjfegm']//*[name()='svg']"))
            )
            close_button.click()
            print("Closed the post view.")
        except TimeoutException:
            print("Couldn't find close button. Navigating back.")
            driver.back()

        time.sleep(2)

    return results

def is_german(text):
    try:
        return detect(text) == 'de'
    except LangDetectException:
        return False

def analyze_sentiment(text, sentiment_analyzer):
    # Get the maximum sequence length for the model
    max_length = sentiment_analyzer.tokenizer.model_max_length

    # Tokenize the text
    tokens = sentiment_analyzer.tokenizer.tokenize(text)

    # If the tokens exceed the maximum length, truncate them
    if len(tokens) > max_length - 2:  # Account for [CLS] and [SEP] tokens
        tokens = tokens[:(max_length - 2)]

    # Convert tokens back to text
    truncated_text = sentiment_analyzer.tokenizer.convert_tokens_to_string(tokens)

    # Analyze sentiment
    result = sentiment_analyzer(truncated_text)
    return int(result[0]['label'].split()[0])



def count_multi_influencer_users(directory):
    user_influencer_count = defaultdict(set)
    for filename in os.listdir(directory):
        if filename.endswith("_comments.json"):
            influencer = filename.split("_comments.json")[0]
            with open(os.path.join(directory, filename), 'r', encoding='utf-8') as file:
                data = json.load(file)
                if isinstance(data, list):
                    for entry in data:
                        if isinstance(entry, dict) and "user" in entry:
                            user_influencer_count[entry["user"]].add(influencer)
                elif isinstance(data, dict):
                    for user in data.keys():
                        user_influencer_count[user].add(influencer)
    
    multi_influencer_users = sum(1 for user, influencers in user_influencer_count.items() if len(influencers) > 1)
    return multi_influencer_users, len(user_influencer_count)


def is_target_language(text, target_lang):
    try:
        return detect(text) == target_lang
    except LangDetectException:
        return False

def merge_and_analyze_comments(directory, target_lang):
    device = "cuda" if torch.cuda.is_available() else "cpu"
    sentiment_analyzer = pipeline("sentiment-analysis", model="nlptown/bert-base-multilingual-uncased-sentiment", device=device)
    print(f"Using device: {device}")

    merged_data = defaultdict(lambda: {"comments": set()})
    very_negative = []
    negative = []
    neutral = []
    positive = []
    positive_target_lang = []

    multi_influencer_users, total_unique_users = count_multi_influencer_users(directory)

    # First, merge all comments from all files
    for filename in os.listdir(directory):
        if filename.endswith("_comments.json"):
            with open(os.path.join(directory, filename), 'r', encoding='utf-8') as file:
                data = json.load(file)
                if isinstance(data, list):
                    for entry in data:
                        if isinstance(entry, dict) and "user" in entry and "comments" in entry:
                            user = entry["user"]
                            comments = entry["comments"]
                            if isinstance(comments, list):
                                merged_data[user]["comments"].update(comments)
                            elif isinstance(comments, str):
                                merged_data[user]["comments"].add(comments)
                elif isinstance(data, dict):
                    for user, comments in data.items():
                        if isinstance(comments, list):
                            merged_data[user]["comments"].update(comments)
                        elif isinstance(comments, str):
                            merged_data[user]["comments"].add(comments)

    total_comments = sum(len(info["comments"]) for info in merged_data.values())
    print(f"Analyzing comments from {total_unique_users} unique users...")
    print(f"Users who commented on multiple influencers' posts: {multi_influencer_users}")

    with tqdm(total=total_comments, desc="Analyzing comments", unit="comment") as pbar:
        for user, info in merged_data.items():
            for comment in info["comments"]:
                sentiment = analyze_sentiment(comment, sentiment_analyzer)
                comment_data = {"user": user, "comment": comment}
                if sentiment == 1:
                    very_negative.append(comment_data)
                elif sentiment == 2:
                    negative.append(comment_data)
                elif sentiment == 3:
                    neutral.append(comment_data)
                else:  # 4 or 5
                    positive.append(comment_data)
                    if is_target_language(comment, target_lang):
                        positive_target_lang.append(comment_data)
                pbar.update(1)

    return merged_data, very_negative, negative, neutral, positive, positive_target_lang, total_unique_users, total_comments, multi_influencer_users

def get_language_selection():
    while True:
        print("\nSelect a language filter:")
        print("1: English")
        print("2: German")
        print("3: Other (specify language code)")
        choice = input("Enter your choice (1, 2, or 3): ")
        
        if choice == '1':
            return 'en'
        elif choice == '2':
            return 'de'
        elif choice == '3':
            lang_code = input("Enter the ISO 639-1 language code (e.g., 'fr' for French): ")
            return lang_code.lower()
        else:
            print("Invalid choice. Please try again.")

def main():
    config = read_config("config.yml")
    username = config['username']
    password = config['password']
    influencers = config['influencers']

    target_lang = get_language_selection()
    lang_name = {'en': 'English', 'de': 'German'}.get(target_lang, target_lang.upper())

    chrome_options = Options()
    chrome_options.add_argument("--lang=en-US")
    chrome_options.add_argument("--disable-notifications")
    chrome_options.add_argument("--start-maximized")

    driver = webdriver.Chrome(service=Service(), options=chrome_options)

    try:
        instagram_login(driver, username, password, "cookies.pkl")
        print("Logged in successfully!")

        # Create a folder with today's date and time
        today_folder = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
        os.makedirs(today_folder, exist_ok=True)

        for influencer in influencers:
            profile_url = influencer['profile_url']
            num_posts = influencer['num_posts']
            print(f"\nScraping comments from: {profile_url} with num_posts set to {num_posts}")

            if num_posts == -1:
                print("Scraping all available posts.")
            comments = scrape_comments(driver, profile_url, num_posts)

            unique_comments = defaultdict(set)
            for user, user_comments in comments.items():
                for comment_text in user_comments:
                    unique_comments[user].add(comment_text)

            final_comments = {user: list(comments) for user, comments in unique_comments.items()}

            output_data = []
            for user, user_comments in final_comments.items():
                user_data = {'user': user, 'comments': user_comments}
                output_data.append(user_data)

            influencer_name = profile_url.rstrip('/').split('/')[-1]
            output_file = os.path.join(today_folder, f"{influencer_name}_comments.json")
            with open(output_file, 'w', encoding='utf-8') as outfile:
                json.dump(output_data, outfile, ensure_ascii=False, indent=4)
            print(f"Comments saved to {output_file}")

        # Analyze comments
        merged_data, very_negative, negative, neutral, positive, positive_target_lang, total_unique_users, total_comments, multi_influencer_users = merge_and_analyze_comments(today_folder, target_lang)

        # Write the merged data to a new JSON file
        output_filename = "merged_comments.json"
        with open(os.path.join(today_folder, output_filename), 'w', encoding='utf-8') as outfile:
            json.dump([{"user": user, "comments": list(info["comments"])} for user, info in merged_data.items()], outfile, ensure_ascii=False, indent=4)

        # Write filtered comments to separate files
        def write_comments(filename, comments):
            with open(os.path.join(today_folder, filename), 'w', encoding='utf-8') as outfile:
                json.dump(comments, outfile, ensure_ascii=False, indent=4)

        write_comments("very_negative_comments.json", very_negative)
        write_comments("negative_comments.json", negative)
        write_comments("neutral_comments.json", neutral)
        write_comments("positive_comments.json", positive)
        write_comments(f"positive_{lang_name.lower()}_comments.json", positive_target_lang)

        # Write usernames to txt files
        def write_usernames(filename, comments):
            with open(os.path.join(today_folder, filename), 'w', encoding='utf-8') as outfile:
                usernames = set(comment['user'] for comment in comments)
                for username in usernames:
                    outfile.write(f"{username}\n")

        write_usernames("positive_usernames.txt", positive)
        write_usernames(f"positive_{lang_name.lower()}_usernames.txt", positive_target_lang)

        print(f"Total unique users: {total_unique_users}")
        print(f"Users who commented on multiple influencers' posts: {multi_influencer_users}")
        print(f"Total comments: {total_comments}")
        print(f"Very negative comments: {len(very_negative)}")
        print(f"Negative comments: {len(negative)}")
        print(f"Neutral comments: {len(neutral)}")
        print(f"Positive comments: {len(positive)}")
        print(f"Positive {lang_name} comments: {len(positive_target_lang)}")

    except Exception as e:
        print(f"An error occurred: {e}")
    finally:
        driver.quit()
        print("Driver closed.")

if __name__ == "__main__":
    main()