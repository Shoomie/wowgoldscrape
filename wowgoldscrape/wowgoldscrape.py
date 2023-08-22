import requests
import sqlite3
import pandas as pd
import json
import time
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from bs4 import BeautifulSoup

BASE_URL = "https://www.wowhead.com/classic/npc="

def connect_db():
    """Connect to the SQLite database and return a connection object."""
    conn = sqlite3.connect('auction_data.db')
    return conn

def update_droprate_and_name(conn, itemId, droprate, itemName):
    """Update droprate and itemName in the database for the given itemId."""
    cursor = conn.cursor()
    cursor.execute("UPDATE auctions SET droprate = ?, itemName = ? WHERE itemId = ?", (droprate, itemName, itemId))
    conn.commit()

def fetch_and_update_item():
    conn = connect_db()
    cursor = conn.cursor()

    # Setup selenium
    chrome_options = Options()
    chrome_options.add_argument("--headless")
    driver = webdriver.Chrome(options=chrome_options)

    cursor.execute("SELECT itemId FROM auctions WHERE droprate IS NULL OR itemName IS NULL ORDER BY marketValue DESC")
    items = cursor.fetchall()

    for item in items:
        item_id = item[0]
        print(str(item_id))

        url = BASE_URL + str(item_id)
        driver.get(url)
        time.sleep(3)
        # Extract droprate
        try:
            droprate_element = driver.find_element(By.XPATH, '//*[@id="tab-dropped-by"]/div[2]/div/table/tbody/tr[1]/td[6]')
            droprate = float(droprate_element.text.replace('%', '').strip())
        except:
            droprate = None
        print(droprate)
        # Extract itemName from the title (taking only text before " - ")
        title = driver.title
        itemName = title.split(" - ")[0].strip() if title else None

        update_droprate_and_name(conn, item_id, droprate, itemName)

    driver.quit()  # Close the browser
    conn.close()

API_KEY = 'MuoSf9xWzcr4hH4sJG0RiIbhBU_fE5Ui'
def generate_tsm_access_token(api_key):
    url = "https://auth.tradeskillmaster.com/oauth2/token"
    payload = {
        "client_id": "c260f00d-1071-409a-992f-dda2e5498536",
        "grant_type": "api_token",
        "scope": "app:realm-api app:pricing-api",
        "token": api_key
    }

    response = requests.post(url, json=payload)

    if response.status_code != 200:
        print(f"Error: {response.status_code} - {response.text}")
        return None

    return response.json().get('access_token')

token = generate_tsm_access_token(API_KEY)

def get_tsm_data(access_token, endpoint):
    headers = {
        "Authorization": f"Bearer {access_token}"
    }
    response = requests.get(endpoint, headers=headers)
    return response.json()

def setup_database(data_sample):
    conn = sqlite3.connect('auction_data.db')
    cursor = conn.cursor()

    # Fetch existing columns
    cursor.execute("PRAGMA table_info(auctions)")
    existing_columns = [column[1] for column in cursor.fetchall()]

    # Create a table for auctions if it doesn't exist
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS auctions (
            id INTEGER PRIMARY KEY
        )
    ''')

    # Dynamically add columns based on JSON keys
    for key in data_sample.keys():
        if key not in existing_columns:
            datatype = "INTEGER"
            if isinstance(data_sample[key], int):
                datatype = "INTEGER"
            elif isinstance(data_sample[key], float):
                datatype = "REAL"
            
            alter_query = f"ALTER TABLE auctions ADD COLUMN {key} {datatype}"
            cursor.execute(alter_query)

    conn.commit()
    return conn

def insert_data_to_db(conn, data):
    cursor = conn.cursor()

    for auction in data:
        columns = ", ".join(auction.keys())
        placeholders = ", ".join("?" * len(auction))
        values = tuple(auction.values())

        # Generate an UPDATE part for the existing columns
        update_part = ", ".join(f"{col} = ?" for col in auction.keys())

        cursor.execute(f'''
            INSERT OR REPLACE INTO auctions ({columns})
            VALUES ({placeholders})
            ON CONFLICT(id) DO UPDATE SET {update_part}
        ''', values*2)  # Duplicate the values for the update part

    conn.commit()


def update_db():
    # Twisting Nether Retail ahID 164
    endpoint = "https://pricing-api.tradeskillmaster.com/ah/164"  # replace with the actual endpoint
    data = get_tsm_data(token, endpoint)

    # Convert the data to a structured JSON string
    structured_json = json.dumps(data, indent=4)

    # Save to a text document
    with open("auctions.json", "w") as f:
        f.write(structured_json)

    print("Data saved to auctions.json")

    # Assuming that the first item in the data list is representative of the structure
    data_sample = data[0] if data else {}

    # Save the data to SQLite
    conn = setup_database(data_sample)
    insert_data_to_db(conn, data)
    conn.close()

fetch_and_update_data()