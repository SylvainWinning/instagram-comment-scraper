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


# Lire la configuration YAML
def read_config(file_path):
    with open(file_path, 'r') as file:
        return yaml.safe_load(file)


# Gestion des cookies pour éviter de se reconnecter à chaque fois
def handle_cookies(driver):
    try:
        WebDriverWait(driver, 10).until(
            EC.element_to_be_clickable((By.XPATH, "//button[contains(text(), 'Allow all cookies')]"))
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


# Connexion à Instagram
def instagram_login(driver, username, password, cookie_file):
    driver.get("https://www.instagram.com/")
    time.sleep(2)  # Attendre que la page se charge

    if not load_cookies(driver, cookie_file):
        driver.find_element(By.NAME, 'username').send_keys(username)
        driver.find_element(By.NAME, 'password').send_keys(password)
        driver.find_element(By.NAME, 'password').send_keys(Keys.ENTER)
        time.sleep(5)  # Attendre pour les éventuelles fenêtres pop-up après la connexion

        handle_cookies(driver)

        # Gérer la fenêtre "Save Your Login Info"
        try:
            WebDriverWait(driver, 10).until(
                EC.element_to_be_clickable((By.XPATH, "//button[contains(text(), 'Save Info')]"))
            ).click()
            print("Login information saved.")
        except TimeoutException:
            print("No prompt to save login information.")

        save_cookies(driver, cookie_file)


# Fonction pour défiler la page et charger plus de commentaires
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


# Scraping des commentaires pour un profil donné
def scrape_comments(driver, profile_url, num_posts):
    driver.get(profile_url)
    time.sleep(3)  # Attendre que la page du profil charge complètement
    posts = driver.find_elements(By.XPATH, "//a[contains(@href, '/p/')]")
    if num_posts != -1:
        posts = posts[:num_posts]

    results = {}
    print(f"Found {len(posts)} posts, processing the latest {num_posts}.")

    for i, post in enumerate(posts):
        print(f"\nProcessing post {i + 1}/{num_posts}")
        post.click()
        time.sleep(3)  # Attendre que le post charge complètement

        # Charger plus de commentaires si disponible
        load_more_count = 0
        while True:
            print("Attempting to load more comments...")
            try:
                load_more_button = WebDriverWait(driver, 5).until(
                    EC.element_to_be_clickable((By.XPATH, "//button//*[contains(text(), 'Load more comments') or contains(text(), 'View more comments')]/.."))
                )
                load_more_button.click()
                load_more_count += 1
                print(f"Clicked 'Load more comments' button {load_more_count} times.")
                time.sleep(2)
            except TimeoutException:
                print(f"No more 'Load more comments' button found. Clicked {load_more_count} times.")
                break

        print("Finished loading comments. Now collecting comment data...")

        # Collecter les commentaires
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

        # Fermer le post
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


# Analyse des commentaires
def analyze_sentiment(text, sentiment_analyzer):
    max_length = sentiment_analyzer.tokenizer.model_max_length
    tokens = sentiment_analyzer.tokenizer.tokenize(text)
    if len(tokens) > max_length - 2:  # Réduire si trop long
        tokens = tokens[:(max_length - 2)]
    truncated_text = sentiment_analyzer.tokenizer.convert_tokens_to_string(tokens)
    result = sentiment_analyzer(truncated_text)
    return int(result[0]['label'].split()[0])


# Programme principal
def main():
    # Lire la configuration
    config = read_config("config.yml")
    username = os.getenv("IG_USERNAME", config['username'])
    password = os.getenv("IG_PASSWORD", config['password'])
    influencers = config['influencers']

    chrome_options = Options()
    chrome_options.add_argument("--lang=en-US")
    chrome_options.add_argument("--disable-notifications")
    chrome_options.add_argument("--start-maximized")

    driver = webdriver.Chrome(service=Service(), options=chrome_options)

    try:
        instagram_login(driver, username, password, "cookies.pkl")
        print("Logged in successfully!")

        today_folder = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
        os.makedirs(today_folder, exist_ok=True)

        for influencer in influencers:
            profile_url = influencer['profile_url']
            num_posts = influencer['num_posts']
            print(f"\nScraping comments from: {profile_url} with num_posts set to {num_posts}")
            comments = scrape_comments(driver, profile_url, num_posts)

            # Sauvegarder les résultats
            output_file = os.path.join(today_folder, f"{profile_url.rstrip('/').split('/')[-1]}_comments.json")
            with open(output_file, 'w', encoding='utf-8') as outfile:
                json.dump(comments, outfile, ensure_ascii=False, indent=4)
            print(f"Comments saved to {output_file}")

    except Exception as e:
        print(f"An error occurred: {e}")
    finally:
        driver.quit()
        print("Driver closed.")


if __name__ == "__main__":
    main()
