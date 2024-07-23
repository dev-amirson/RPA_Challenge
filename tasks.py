import logging
import os
import requests
from datetime import datetime, timedelta
from bs4 import BeautifulSoup
import pandas as pd
import time
from robocorp import browser
from robocorp.tasks import task
from dotenv import load_dotenv
load_dotenv()

# Initialize the logger
logging.basicConfig(
    filename='news_scraper.log',
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
)

logger = logging.getLogger(__name__)

# Using OOP
class NewsScraper:
    def __init__(self, search_phrase, category, selector, limit):
        self.search_phrase = search_phrase
        self.category = category
        self.selector = selector
        self.limit = limit
        self.search_time = datetime.now()
        self.search_date = self.search_time.strftime("%B %d %Y")
        self.extracted_data = []
        self.image_count = 0  # Counter for image filenames
        logger.debug(f'Initialized NewsScraper with search_phrase="{search_phrase}", category={category}, selector="{selector}", limit={limit}')

    def parse_and_format_date(self, date_string):
        """
        Changes time format to match
        """
        logger.debug(f'Parsing date string: {date_string}')
        current_date = datetime.strptime(self.search_date, "%B %d %Y")
        if date_string == "No date found":
            return self.search_date
        elif "min ago" in date_string or "mins ago" in date_string: 
            return self.search_date
        elif date_string == "Yesterday":
            parsed_date = current_date - timedelta(days=1)
        elif "hours ago" in date_string or "hour ago" in date_string:
            hours = int(date_string.split()[0])
            parsed_date = current_date - timedelta(hours=hours)
        elif "days ago" in date_string or "day ago" in date_string:
            days = int(date_string.split()[0])
            parsed_date = current_date - timedelta(days=days)
        else:
            try:
                # Try parsing the date string
                parsed_date = datetime.strptime(date_string, "%B %d")
                # If successful, set the year to the current year
                parsed_date = parsed_date.replace(year=current_date.year)
            except ValueError:
                try:
                    # If the above fails, try parsing with year included
                    parsed_date = datetime.strptime(date_string, "%B %d %Y")
                except ValueError:
                    # If all parsing attempts fail, return the original string
                    logger.warning(f'Failed to parse date string: {date_string}')
                    return date_string

        # Format the parsed date
        formatted_date = parsed_date.strftime("%B %d %Y")
        logger.debug(f'Parsed date string: {date_string} to {formatted_date}')
        return formatted_date

    def configure_browser(self):
        logger.info('Configuring browser')
        browser.configure(
            browser_engine="chromium",
            screenshot="only-on-failure",
            headless=False,
        )

    def navigate_and_search(self):
        logger.info('Starting navigation and search')
        try:
            # Navigate to the website
            page = browser.goto("https://apnews.com")
            time.sleep(5)
            
            # Privacy policy button
            page.wait_for_selector("div.has-reject-all-button div.banner-actions-container button")
            page.click("div.has-reject-all-button div.banner-actions-container button")
            logger.debug('Clicked privacy policy button')

            # Wait for the search button to be visible and click it
            page.wait_for_selector("button.SearchOverlay-search-button")
            page.click("button.SearchOverlay-search-button")
            logger.debug('Clicked search button')

            # Wait for the search input to be visible and fill it out
            search_input_selector = "input.SearchOverlay-search-input"
            page.wait_for_selector(search_input_selector)
            page.fill(search_input_selector, self.search_phrase)
            logger.debug(f'Filled search input with phrase: {self.search_phrase}')

            # Optionally, submit the search form
            page.press(search_input_selector, "Enter")

            page.wait_for_selector("div.SearchResultsModule-filters-content")

            # Click on the "Category" filter to expand it
            page.click("div.SearchFilter-heading[data-toggle-trigger='search-filter']")

            # Wait for the filter options to be visible
            page.wait_for_selector("div.SearchFilter-items-wrapper")

            # Select the desired filter checkbox inputs by their values
            if self.category[0]:
                page.check("input[name='f2'][value='00000190-0dc5-d7b0-a1fa-dde7ec030000']")  # Live Blogs
                logger.debug('Selected Live Blogs category')
        
            if self.category[1]:
                page.check("input[name='f2'][value='00000188-f942-d221-a78c-f9570e360000']")  # Stories
                logger.debug('Selected Stories category')
            
            page.press(search_input_selector, "Enter")
            page.reload()

            sort_dropdown_selector = "select.Select-input"
            
            page.wait_for_selector("div.PageList-items div.PageList-items-item", timeout=10000)

            # Select the "Newest" option from the dropdown
            page.select_option(sort_dropdown_selector, self.selector)
            logger.debug(f'Selected sort option: {self.selector}')

            page.reload()
            time.sleep(5)

            self.extract_data(page)

        finally:
            # Playwright handles browser closing        
            self.save_data()

    def download_image(self, url, output_folder="output"):
        if not os.path.exists(output_folder):
            os.makedirs(output_folder)

        self.image_count += 1  # Increment the image counter
        image_name = f"image_{self.image_count}.jpeg"
        image_path = os.path.join(output_folder, image_name)

        try:
            response = requests.get(url, stream=True)
            response.raise_for_status()

            with open(image_path, "wb") as file:
                for chunk in response.iter_content(1024):
                    file.write(chunk)

            return image_name
        except Exception as e:
            logger.error(f"Failed to download image from {url}: {e}")
            return "Download failed"

    def extract_data(self, page):
        logger.info('Extracting data')
        money_phrases = ["dollar", "dollars", "$"]
        while self.limit > 0:
            stories = page.locator("div.SearchResultsModule-results div.PageList-items div.PageList-items-item")
            story_count = stories.count()

            for i in range(story_count):
                story_html = stories.nth(i).inner_html()
                soup = BeautifulSoup(story_html, 'html.parser')

                # Extract Title
                title_elem = soup.select_one('div.PagePromo-title a')            
                title = title_elem.text.strip() if title_elem else 'N/A'
                
                lowercase_title= title.lower()
                lowercase_phrase= self.search_phrase.lower()
                phrase_count = lowercase_title.count(lowercase_phrase)
                
                money_flag = False
                if any(phrase.lower() in title.lower() for phrase in money_phrases):
                    money_flag = True 

                # Extract Description
                descirption_elem = soup.select_one('div.PagePromo-content div.PagePromo-description span.PagePromoContentIcons-text')
                description=descirption_elem.text.strip() if descirption_elem else 'N/A'

                # Extract Link
                link_elem = soup.select_one('div.PagePromo-content a')
                link = link_elem['href'] if link_elem and 'href' in link_elem.attrs else 'No link found'

                # Extract Image (if available)
                img_elem = soup.select_one('picture img.Image')
                image_src = img_elem['src'] if img_elem and 'src' in img_elem.attrs else 'No image found'
                image_name = self.download_image(image_src) if image_src != 'No image found' else 'No image found'

                # Extract Date
                date_elem = soup.select_one('div.PagePromo-content div.PagePromo-byline div.PagePromo-date span[data-date] span.Timestamp-template')
                date = date_elem.text.strip() if date_elem else 'No date found'
                news_date = self.parse_and_format_date(date)

                self.extracted_data.append({
                    'Search_Phrase': self.search_phrase,
                    'Phrase_Count': phrase_count, 
                    'Title': title,
                    'Description': description,
                    'Money_Flag': money_flag, 
                    'Image_Name': image_name,
                    'Image_URL': image_src,
                    'Link': link,
                    'News_Date': news_date, 
                    'Search Date': self.search_date, 
                })

                logger.debug(f'Extracted story: {title}')

            page.wait_for_selector("div.Pagination div.Pagination-nextPage")
            page.click("div.Pagination div.Pagination-nextPage a")
            time.sleep(10)
            self.limit -= 1
            time.sleep(10)

    def save_data(self):
        logger.info('Saving extracted data')
        # Save extracted data to a file
        df = pd.DataFrame(self.extracted_data)
        # Save DataFrame to an Excel file
        df.to_excel("output/extracted_story_data.xlsx", index=False, engine='openpyxl')
        logger.info('Data saved to output/extracted_story_data.xlsx')

@task
def search_keyword():
    logger.info('Starting search_keyword task')
    search_phrase = os.environ["SEARCH"]
    category = [os.environ["STORIES"].lower() == 'true', 
    os.environ["BLOG"].lower() == 'true']
    selector = os.environ["SELECTOR"]
    limit = int(os.environ["LIMIT"])

    scraper = NewsScraper(search_phrase, category, selector, limit)
    scraper.configure_browser()
    scraper.navigate_and_search()

if __name__ == "__main__":
    search_keyword()
