import pandas as pd
import time
import random
import os
import json
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, NoSuchElementException, ElementClickInterceptedException
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.keys import Keys

# Global variables
driver = None
processed_profiles = {"liked": [], "messaged": []}

def setup_driver():
    """Set up the Chrome driver with anti-detection measures."""
    chrome_options = Options()
    
    # Anti-detection measures
    chrome_options.add_argument("--disable-blink-features=AutomationControlled")
    chrome_options.add_experimental_option("excludeSwitches", ["enable-automation"])
    chrome_options.add_experimental_option("useAutomationExtension", False)
    
    # Additional options to make the browser more human-like
    chrome_options.add_argument("--start-maximized")
    chrome_options.add_argument("--disable-infobars")
    chrome_options.add_argument("--disable-extensions")
    
    # User agent to mimic a real browser
    user_agents = [
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/99.0.4844.84 Safari/537.36",
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/99.0.4844.83 Safari/537.36"
    ]
    chrome_options.add_argument(f"user-agent={random.choice(user_agents)}")
    
    global driver
    driver = webdriver.Chrome(options=chrome_options)
    
    # Modify navigator properties to avoid detection
    driver.execute_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
    return driver

def load_processed_profiles(filename="processed_profiles.json"):
    """Load the list of already processed profiles from file."""
    global processed_profiles
    if os.path.exists(filename):
        try:
            with open(filename, 'r') as f:
                processed_profiles = json.load(f)
        except Exception as e:
            print(f"Error loading processed profiles: {e}")
            processed_profiles = {"liked": [], "messaged": []}
    return processed_profiles

def save_processed_profile(profile_id, action_type, filename="processed_profiles.json"):
    """Save the profile ID to the processed list."""
    global processed_profiles
    if profile_id not in processed_profiles[action_type]:
        processed_profiles[action_type].append(profile_id)
        with open(filename, 'w') as f:
            json.dump(processed_profiles, f)
        print(f"Saved profile {profile_id} to {action_type} list")

def extract_profile_id(profile_url):
    """Extract the Facebook profile ID from the URL."""
    # Different patterns of Facebook URLs
    if "user/" in profile_url:
        # Pattern: .../user/100087040762170/
        parts = profile_url.split("user/")
        if len(parts) > 1:
            user_id = parts[1].strip("/")
            return user_id
    elif "profile.php?id=" in profile_url:
        # Pattern: .../profile.php?id=100087040762170
        parts = profile_url.split("profile.php?id=")
        if len(parts) > 1:
            user_id = parts[1].split("&")[0]
            return user_id
            
    # If we can't extract the ID, use the whole URL as a unique identifier
    return profile_url

def is_profile_processed(profile_id, action_type):
    """Check if the profile has already been processed for this action type."""
    global processed_profiles
    return profile_id in processed_profiles[action_type]

def add_random_delay(min_sec=1, max_sec=3):
    """Add a random delay to mimic human behavior."""
    time.sleep(random.uniform(min_sec, max_sec))

def human_type(element, text):
    """Type text like a human with random delays between keystrokes."""
    try:
        element.click()  # Make sure element is focused
        add_random_delay(0.2, 0.5)
        
        for char in text:
            element.send_keys(char)
            time.sleep(random.uniform(0.05, 0.2))
            
        # Add a small pause after typing
        add_random_delay(0.5, 1)
    except Exception as e:
        print(f"Error typing text: {e}")
        # Try direct typing as a fallback
        element.send_keys(text)

def login(email, password, cookies_path="fb_cookies.pkl"):
    """Login to Facebook using credentials or cookies."""
    driver.get("https://www.facebook.com")
    
    # Check if cookies exist and use them
    if os.path.exists(cookies_path):
        try:
            import pickle
            cookies = pickle.load(open(cookies_path, "rb"))
            for cookie in cookies:
                driver.add_cookie(cookie)
            driver.refresh()
            
            # Verify if login was successful
            add_random_delay(3, 5)
            if "facebook.com/home" in driver.current_url or check_if_logged_in():
                print("Logged in using cookies")
                return True
            else:
                print("Cookie login failed, falling back to credentials")
        except Exception as e:
            print(f"Error loading cookies: {e}")
    
    # If cookies don't exist or fail, use credentials
    try:
        # Accept cookies if prompted
        try:
            cookie_button = WebDriverWait(driver, 5).until(
                EC.element_to_be_clickable((By.XPATH, "//button[contains(string(), 'Allow') or contains(string(), 'Accept') or contains(string(), 'Only allow essential cookies')]"))
            )
            cookie_button.click()
            time.sleep(random.uniform(1, 2))
        except (TimeoutException, NoSuchElementException):
            pass
        
        # Enter email
        email_field = WebDriverWait(driver, 10).until(
            EC.presence_of_element_located((By.ID, "email"))
        )
        human_type(email_field, email)
        
        # Enter password
        password_field = driver.find_element(By.ID, "pass")
        human_type(password_field, password)
        
        # Click login button
        login_button = driver.find_element(By.NAME, "login")
        login_button.click()
        
        # Wait for login to complete
        time.sleep(random.uniform(5, 7))
        
        # Check if login successful
        if "facebook.com/home" in driver.current_url or check_if_logged_in():
            # Save cookies for future use
            import pickle
            pickle.dump(driver.get_cookies(), open(cookies_path, "wb"))
            print("Login successful, cookies saved")
            return True
        else:
            print("Login failed - check credentials or possible security checks")
            return False
        
    except Exception as e:
        print(f"Login failed: {e}")
        return False

def check_if_logged_in():
    """Check if we're logged in by looking for common elements."""
    try:
        # Check for elements that exist only when logged in
        WebDriverWait(driver, 5).until(
            EC.presence_of_element_located((By.XPATH, "//div[@aria-label='Your profile' or @aria-label='Account' or contains(@aria-label, 'Profile')]"))
        )
        return True
    except:
        return False

def close_chat_window():
    """Close any open chat windows."""
    try:
        # Try multiple selectors for chat close buttons
        close_chat_selectors = [
            "//div[@aria-label='Close chat' or @aria-label='Close Chat']",
            "//div[@role='button' and contains(@aria-label, 'Close')]",
            "//div[@role='button' and contains(@style, 'right') and contains(@style, 'top')]//div[@role='button']",
            "//div[@data-testid='messenger_dialog_close_button']"
        ]
        
        for selector in close_chat_selectors:
            try:
                close_buttons = driver.find_elements(By.XPATH, selector)
                for button in close_buttons:
                    button.click()
                    add_random_delay(0.5, 1)
                    print("Closed a chat window")
            except:
                continue
        
        # Check if we need to minimize any chat windows
        minimize_selectors = [
            "//div[@aria-label='Minimize chat' or contains(@aria-label, 'Minimize')]",
            "//div[@role='button' and contains(@style, 'height') and contains(@style, 'width')]//div[@role='button']"
        ]
        
        for selector in minimize_selectors:
            try:
                minimize_buttons = driver.find_elements(By.XPATH, selector)
                for button in minimize_buttons:
                    button.click()
                    add_random_delay(0.5, 1)
                    print("Minimized a chat window")
            except:
                continue
                
        # Try to press Escape key to close any remaining windows
        try:
            webdriver.ActionChains(driver).send_keys(Keys.ESCAPE).perform()
            add_random_delay(0.5, 1)
            webdriver.ActionChains(driver).send_keys(Keys.ESCAPE).perform()
        except:
            pass
            
    except Exception as e:
        print(f"Error closing chat windows: {e}")

def like_profile_picture(profile_url, profile_id):
    """Navigate to profile and like the profile picture if possible."""
    # Check if we've already liked this profile
    if is_profile_processed(profile_id, "liked"):
        print(f"Already liked profile picture for {profile_id}")
        return True
        
    try:
        # Navigate to profile
        driver.get(profile_url)
        add_random_delay(2, 4)
        
        # First approach: Try to access the profile picture directly
        try:
            # Multiple possible selectors for profile pictures
            profile_pic_selectors = [
                "//a[contains(@href, 'photo.php') or contains(@href, '/photo/')]",
                "//div[contains(@aria-label, 'profile photo') or contains(@aria-label, 'Profile picture')]//a",
                "//a[@role='link' and contains(@href, 'photo')]//img[contains(@alt, 'profile picture')]",
                "//a[contains(@href, 'profile/picture')]"
            ]
            
            profile_pic = None
            for selector in profile_pic_selectors:
                try:
                    profile_pics = driver.find_elements(By.XPATH, selector)
                    if profile_pics:
                        profile_pic = profile_pics[0]
                        break
                except Exception as e:
                    print(f"Selector failed: {e}")
                    continue
            
            if profile_pic:
                # Click on the profile picture
                driver.execute_script("arguments[0].click();", profile_pic)
                add_random_delay(2, 3)
                
                # Check if we successfully opened the photo overlay
                overlay_selectors = [
                    "//div[@role='dialog']",
                    "//div[contains(@aria-label, 'Photo viewer')]",
                    "//div[@aria-modal='true']"
                ]
                
                overlay_present = False
                for selector in overlay_selectors:
                    try:
                        overlay = WebDriverWait(driver, 3).until(
                            EC.presence_of_element_located((By.XPATH, selector))
                        )
                        overlay_present = True
                        break
                    except:
                        continue
                
                if not overlay_present:
                    # If we didn't get an overlay, try alternative approach
                    raise Exception("Photo overlay not detected")
                
                # Alternative approach for likes: Look for reactions or like buttons inside the overlay
                like_button_selectors = [
                    "//div[@aria-label='Like' or contains(@aria-label, 'Like')]",
                    "//span[text()='Like']/parent::div[@role='button']",
                    "//div[@role='button' and contains(., 'Like')]",
                    "//div[contains(@class, 'x1i10hfl') and @role='button' and contains(., 'Like')]",
                    "//div[@role='button' and .//*[local-name()='svg' and contains(@style, 'like')]]"
                ]
                
                like_button = None
                for selector in like_button_selectors:
                    try:
                        like_buttons = driver.find_elements(By.XPATH, selector)
                        if like_buttons:
                            # Filter out buttons that are likely to be "Already liked"
                            for btn in like_buttons:
                                try:
                                    # Check if button doesn't have aria-pressed="true" or "active" class
                                    if (btn.get_attribute("aria-pressed") != "true" and 
                                       "active" not in btn.get_attribute("class")):
                                        like_button = btn
                                        break
                                except:
                                    # If we can't check attributes, just use the first button
                                    like_button = btn
                            if like_button:
                                break
                    except:
                        continue
                
                if like_button:
                    # Try JavaScript click which can bypass some overlay issues
                    try:
                        driver.execute_script("arguments[0].click();", like_button)
                        print(f"Liked profile picture for {profile_id}")
                        add_random_delay(1, 2)
                    except Exception as e:
                        print(f"Failed to click like button with JS: {e}")
                        # Try direct click as fallback
                        try:
                            like_button.click()
                            print(f"Liked profile picture for {profile_id} with direct click")
                        except:
                            print(f"Could not like photo for {profile_id}")
                else:
                    # Second fallback: try to find reaction buttons
                    reaction_selectors = [
                        "//div[@aria-label='Reactions' or contains(@aria-label, 'reaction')]",
                        "//div[@aria-label='React']",
                        "//div[contains(@aria-label, 'Reaction options')]"
                    ]
                    
                    for selector in reaction_selectors:
                        try:
                            reaction_button = WebDriverWait(driver, 3).until(
                                EC.element_to_be_clickable((By.XPATH, selector))
                            )
                            reaction_button.click()
                            add_random_delay(1, 2)
                            
                            # Now try to click specifically on "Like" in the reaction menu
                            like_reaction = WebDriverWait(driver, 3).until(
                                EC.element_to_be_clickable((By.XPATH, "//div[@role='button' and contains(@aria-label, 'Like')]"))
                            )
                            like_reaction.click()
                            print(f"Liked profile picture via reactions for {profile_id}")
                            add_random_delay(1, 2)
                            break
                        except:
                            continue
                            
                # Try to close the photo once we're done
                close_buttons = [
                    "//div[@aria-label='Close' or @aria-label='Close dialog']",
                    "//div[@aria-label='Back']",
                    "//div[@aria-label='Close photo']",
                    "//div[@role='button' and @tabindex='0' and contains(@style, 'height') and contains(@style, 'width')]"
                ]
                
                close_success = False
                for close_selector in close_buttons:
                    try:
                        close_buttons = driver.find_elements(By.XPATH, close_selector)
                        if close_buttons:
                            driver.execute_script("arguments[0].click();", close_buttons[0])
                            close_success = True
                            break
                    except:
                        continue
                        
                if not close_success:
                    # Escape key fallback
                    try:
                        webdriver.ActionChains(driver).send_keys(Keys.ESCAPE).perform()
                    except:
                        # Navigation fallback if everything else fails
                        driver.get(profile_url)
            else:
                # Second approach: Try checking if there are any "View profile picture" options
                try:
                    view_buttons = driver.find_elements(By.XPATH, "//span[contains(text(), 'View profile picture')]")
                    if view_buttons:
                        driver.execute_script("arguments[0].click();", view_buttons[0])
                        add_random_delay(2, 3)
                        
                        # Then try liking with the normal approach
                        like_button = WebDriverWait(driver, 5).until(
                            EC.element_to_be_clickable((By.XPATH, "//div[@aria-label='Like' or contains(@aria-label, 'Like')]"))
                        )
                        like_button.click()
                        print(f"Liked profile picture via 'View profile picture' for {profile_id}")
                        add_random_delay(1, 2)
                        
                        # Close the picture
                        close_button = WebDriverWait(driver, 3).until(
                            EC.element_to_be_clickable((By.XPATH, "//div[@aria-label='Close' or @aria-label='Close dialog']"))
                        )
                        close_button.click()
                    else:
                        print(f"No interaction possible with profile picture for {profile_id}")
                except:
                    print(f"Could not interact with profile picture for {profile_id}")
                    
            # Third approach: Try hovering on profile pic for popup and like there
            try:
                profile_images = driver.find_elements(By.XPATH, "//img[contains(@alt, 'profile picture') or contains(@alt, 'Profile photo')]")
                if profile_images:
                    # Hover over the image
                    hover = webdriver.ActionChains(driver).move_to_element(profile_images[0])
                    hover.perform()
                    add_random_delay(1, 2)
                    
                    # Look for like button in popup
                    popup_like = driver.find_element(By.XPATH, "//div[@role='button' and contains(., 'Like')]")
                    if popup_like:
                        popup_like.click()
                        print(f"Liked profile picture via hover popup for {profile_id}")
                        add_random_delay(1, 2)
            except:
                pass
                
        except Exception as e:
            print(f"Could not interact with profile picture: {e}")
            
        # Mark profile as liked regardless - we tried our best
        save_processed_profile(profile_id, "liked")
        return True
            
    except Exception as e:
        print(f"Error liking profile picture: {e}")
        # Mark as processed to avoid getting stuck on problematic profiles
        save_processed_profile(profile_id, "liked")
        return False

def send_message(profile_url, profile_id, message):
    """Send a custom message to the profile."""
    # Check if we've already messaged this profile
    if is_profile_processed(profile_id, "messaged"):
        print(f"Already messaged profile {profile_id}")
        return True
        
    try:
        # Navigate to profile
        driver.get(profile_url)
        add_random_delay(2, 4)
        
        # Find and click the message button (try multiple selectors)
        message_button_selectors = [
            "//div[contains(text(), 'Message') or contains(@aria-label, 'Message')]",
            "//a[contains(@href, '/messages/') and contains(text(), 'Message')]",
            "//span[text()='Message']/parent::div",
            "//div[@role='button' and contains(., 'Message')]"
        ]
        
        message_button = None
        for selector in message_button_selectors:
            try:
                message_button = WebDriverWait(driver, 5).until(
                    EC.element_to_be_clickable((By.XPATH, selector))
                )
                break
            except (TimeoutException, NoSuchElementException):
                continue
        
        if message_button is None:
            print(f"Message button not found for {profile_id}, marking as processed")
            save_processed_profile(profile_id, "messaged")
            return False
            
        message_button.click()
        add_random_delay(2, 3)
        
        # Wait for the message dialog to appear and find the message box
        message_box_selectors = [
            "//div[@contenteditable='true' and @role='textbox']",
            "//div[@aria-label='Message' and @contenteditable='true']",
            "//div[@data-contents='true']//div[@data-contents='true']",
            "//div[contains(@class, 'notranslate') and @contenteditable='true']"
        ]
        
        message_box = None
        for selector in message_box_selectors:
            try:
                message_box = WebDriverWait(driver, 8).until(
                    EC.presence_of_element_located((By.XPATH, selector))
                )
                break
            except (TimeoutException, NoSuchElementException):
                continue
        
        if message_box is None:
            print(f"Message box not found for {profile_id}, marking as processed")
            save_processed_profile(profile_id, "messaged")
            # Try to close any open chat windows
            close_chat_window()
            return False
        
        # Clear existing text if any
        try:
            message_box.clear()
        except:
            pass
            
        # Type the message with human-like behavior
        try:
            human_type(message_box, message)
        except Exception as e:
            print(f"Error typing message: {e}")
            try:
                # Direct method as fallback
                message_box.send_keys(message)
            except:
                print(f"Could not type message to {profile_id}")
                save_processed_profile(profile_id, "messaged")
                # Try to close any open chat windows
                close_chat_window()
                return False
        
        # Find and click the send button
        send_button_selectors = [
            "//div[@aria-label='Press Enter to send']",
            "//button[contains(@aria-label, 'Send') or contains(@aria-label, 'send')]",
            "//div[@role='button' and contains(@aria-label, 'Send')]",
            "//div[@role='button' and @tabindex='0' and contains(@style, 'right')]"
        ]
        
        send_button = None
        for selector in send_button_selectors:
            try:
                send_button = WebDriverWait(driver, 5).until(
                    EC.element_to_be_clickable((By.XPATH, selector))
                )
                break
            except (TimeoutException, NoSuchElementException):
                continue
        
        if send_button is None:
            print(f"Send button not found for {profile_id}, trying Enter key")
            # Try pressing Enter as a fallback
            try:
                message_box.send_keys(Keys.ENTER)
                add_random_delay(1, 2)
            except Exception as e:
                print(f"Failed to send message with Enter key: {e}")
                save_processed_profile(profile_id, "messaged")
                # Try to close any open chat windows
                close_chat_window()
                return False
        else:
            # Click the send button
            send_button.click()
        
        add_random_delay(2, 3)
        
        # Close the chat window after sending
        close_chat_window()
        
        # Mark profile as messaged
        save_processed_profile(profile_id, "messaged")
        print(f"Message sent to {profile_id}")
        return True
        
    except Exception as e:
        print(f"Error sending message: {e}")
        # Mark as processed to avoid getting stuck
        save_processed_profile(profile_id, "messaged")
        # Try to close any open chat windows
        close_chat_window()
        return False

def random_scroll():
    """Perform random scrolling to seem more human-like."""
    scroll_amount = random.randint(100, 500)
    driver.execute_script(f"window.scrollBy(0, {scroll_amount});")
    add_random_delay(0.5, 1.5)

def random_activity():
    """Perform some random activity to seem more human-like."""
    try:
        # Navigate to Facebook homepage
        driver.get("https://www.facebook.com")
        add_random_delay(2, 4)
        
        # Random scrolling
        for _ in range(random.randint(2, 5)):
            random_scroll()
            
        # Possibly click on a few things
        if random.random() < 0.3:  # 30% chance
            try:
                # Try to find some non-disruptive elements to click
                elements = driver.find_elements(By.XPATH, "//span[contains(text(), 'Like') or contains(text(), 'Comment') or contains(text(), 'Share')]")
                if elements and len(elements) > 0:
                    random.choice(elements).click()
                    add_random_delay()
            except:
                pass
                
    except Exception as e:
        print(f"Error during random activity: {e}")

def process_csv(csv_file, custom_message, interval_min=30, interval_max=60):
    """Process the CSV file and interact with profiles."""
    try:
        # Read the CSV file
        df = pd.read_csv(csv_file)
        
        # Get the column names
        columns = df.columns.tolist()
        url_column = columns[0]
        name_column = columns[1]
        
        # Process each row
        for index, row in df.iterrows():
            profile_url = row[url_column]
            name = row[name_column]
            
            # Extract profile ID
            profile_id = extract_profile_id(profile_url)
            
            # Personalize the message with the name
            personalized_message = custom_message.replace("{name}", name)
            
            print(f"Processing profile: {name} ({profile_id})")
            
            # Check if already processed both actions
            if is_profile_processed(profile_id, "liked") and is_profile_processed(profile_id, "messaged"):
                print(f"Profile {profile_id} already fully processed, skipping")
                continue
            
            # Like profile picture if not already liked
            if not is_profile_processed(profile_id, "liked"):
                like_success = like_profile_picture(profile_url, profile_id)
                # Add a random delay between actions
                add_random_delay(2, 5)
            
            # Send message if not already messaged
            if not is_profile_processed(profile_id, "messaged"):
                message_success = send_message(profile_url, profile_id, personalized_message)
                # Make sure any chat windows are closed
                close_chat_window()
            
            # Add a longer random delay between profiles to avoid detection
            wait_time = random.uniform(interval_min, interval_max)
            print(f"Waiting {wait_time:.2f} seconds before the next profile...")
            time.sleep(wait_time)
            
    except Exception as e:
        print(f"Error processing CSV: {e}")
        # Try to close any open chat windows
        close_chat_window()

def main():
    # Configuration
    email = "pavot75975@aqqor.com"
    password = "Oponghta"
    csv_file = "ppl.csv"
    custom_message = "."
    
    # Set up the driver
    global driver
    driver = setup_driver()
    
    # Load processed profiles
    load_processed_profiles()
    
    try:
        # Login
        login_success = login(email, password)
        
        if login_success:
            # Perform some random activity first to look more human
            random_activity()
            
            # Process the CSV file with a delay of 30-60 seconds between profiles
            process_csv(csv_file, custom_message, interval_min=30, interval_max=60)
            
            # Final random activity
            random_activity()
    
    except Exception as e:
        print(f"Error in main function: {e}")
    
    finally:
        # Clean up
        if driver:
            driver.quit()

if __name__ == "__main__":
    main()
