from robocorp import browser
from robocorp.tasks import task
from datetime import datetime, timedelta
from bs4 import BeautifulSoup
import pandas as pd
import time, os
from dotenv import load_dotenv
load_dotenv()

# Add an env file with these variables, sample values also provided
# SEARCH="obama"
# STORIES=True
# BLOG=True
# SELECTOR="3"
# LIMIT=5

def parse_and_format_date(date_string, search_date):
    """
    Changes time format to match
    """
    current_date = datetime.strptime(search_date, "%B %d %Y")
    if date_string == "No date found":
        return search_date
    elif "min ago" in date_string or "mins ago"  in date_string: 
        return search_date
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
                return date_string

    # Format the parsed date
    return parsed_date.strftime("%B %d %Y")

@task
def search_keyword():
    """
    Navigate to temp.com, click the search button, and fill out the search input field.
    """
    category = [False, False]
    search_phrase = os.environ["SEARCH"]

    # Convert string to boolean
    category[0] = os.environ["STORIES"].lower() == 'true'
    category[1] = os.environ["BLOG"].lower() == 'true'

    selector = os.environ["SELECTOR"]
    limit = int(os.environ["LIMIT"])

    search_time = datetime.now()
    search_date = search_time.strftime("%B %d %Y")

    browser.configure(
        browser_engine="chromium",
        screenshot="only-on-failure",
        headless=False,
    )

    extracted_data = []

    try:
        # Navigate to the website
        page = browser.goto("https://apnews.com")
        time.sleep(5)
      
        # privacy policy button
        page.wait_for_selector("div.has-reject-all-button div.banner-actions-container button")
        page.click("div.has-reject-all-button div.banner-actions-container button")
 
        # Wait for the search button to be visible and click it
        page.wait_for_selector("button.SearchOverlay-search-button")
        page.click("button.SearchOverlay-search-button")

        # Wait for the search input to be visible and fill it out
        search_input_selector = "input.SearchOverlay-search-input"
        page.wait_for_selector(search_input_selector)
        page.fill(search_input_selector, search_phrase)

        # Optionally, submit the search form
        page.press(search_input_selector, "Enter")
        # page.screenshot()

        page.wait_for_selector("div.SearchResultsModule-filters-content")

        # Click on the "Category" filter to expand it
        page.click("div.SearchFilter-heading[data-toggle-trigger='search-filter']")

        # Wait for the filter options to be visible
        page.wait_for_selector("div.SearchFilter-items-wrapper")

        # Select the desired filter checkbox inputs by their values
        if category[0]:
           page.check("input[name='f2'][value='00000190-0dc5-d7b0-a1fa-dde7ec030000']")  # Live Blogs
    
        if category[1]:
            page.check("input[name='f2'][value='00000188-f942-d221-a78c-f9570e360000']")  # Stories
        
        page.press(search_input_selector, "Enter")
        page.reload()

        sort_dropdown_selector = "select.Select-input"
        
        page.wait_for_selector("div.PageList-items div.PageList-items-item", timeout=10000)

        # Select the "Newest" option from the dropdown
        page.select_option(sort_dropdown_selector, selector)

        page.reload()
        time.sleep(5)

        while (limit>0):

            stories = page.locator("div.SearchResultsModule-results div.PageList-items div.PageList-items-item")
            story_count = stories.count()

            for i in range(story_count):
                story_html = stories.nth(i).inner_html()
                soup = BeautifulSoup(story_html, 'html.parser')

                # Extract Title
                title_elem = soup.select_one('div.PagePromo-title a')            
                title = title_elem.text.strip() if title_elem else 'N/A'

                # Extract Link
                link_elem = soup.select_one('div.PagePromo-content a')
                link = link_elem['href'] if link_elem and 'href' in link_elem.attrs else 'No link found'

                # Extract Image (if available)
                img_elem = soup.select_one('picture img.Image')
                image_src = img_elem['src'] if img_elem and 'src' in img_elem.attrs else 'No image found'

                # Extract Date
                date_elem = soup.select_one('div.PagePromo-content div.PagePromo-byline div.PagePromo-date span[data-date] span.Timestamp-template')
                date = date_elem.text.strip() if date_elem else 'No date found'
                new_date = parse_and_format_date(date, search_date)
        
                extracted_data.append({
                    'Title': title,
                    'Link': link,
                    'Image': image_src,
                    'Date': new_date, 
                    'Search Date': search_date, 
                })

            page.wait_for_selector("div.Pagination div.Pagination-nextPage")
            page.click("div.Pagination div.Pagination-nextPage a")
            time.sleep(10)
            limit-=1

        time.sleep(10)        

    finally:
        # Playwright handles browser closing        
        
        # Save extracted data to a file
        df = pd.DataFrame(extracted_data)
        
        # Save DataFrame to an Excel file
        df.to_excel("output/extracted_story_data.xlsx", index=False, engine='openpyxl')

        print('Done')

if __name__ == "__main__":
    search_keyword()