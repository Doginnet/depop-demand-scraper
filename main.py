import json
from datetime import datetime
from pathlib import Path
from curl_cffi import requests

RAW_DIR = Path(__file__).parent / "raw"

def save_raw_json(data: dict | list, filename_prefix: str = "response") -> Path:
    RAW_DIR.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    file_path = RAW_DIR / f"{filename_prefix}_{timestamp}.json"
    with open(file_path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    print(f"Saved raw JSON to {file_path}")
    return file_path

limit = 160 # max offset is 3000, but the api wouldn't return more than 160 results for one call 
# good idea is to make first request to figure out the total count 
# for the baggy jeans search it is aroun 782000
# We need to filter out only those that are trending via likes or offers
# set the likes threshold to 10 


def main():
    url = f"https://www.depop.com/presentation/api/v1/search/products/?what=baggy+jeans&after=&limit={limit}&country=us&currency=USD&from=in_country_search&include_like_count=true"
    
    headers = {
        "accept": "application/json, text/plain, */*",
        "accept-language": "en-US,en;q=0.9",
        "origin": "https://www.depop.com",
        "referer": "https://www.depop.com/",
        "sec-ch-ua": '"Chromium";v="124", "Google Chrome";v="124", "Not-A.Brand";v="99"',
        "sec-ch-ua-mobile": "?0",
        "sec-ch-ua-platform": '"Windows"',
        "sec-fetch-dest": "empty",
        "sec-fetch-mode": "cors",
        "sec-fetch-site": "same-site",
    }

    session = requests.Session(impersonate="chrome124")
    # First warm-up visit main site for cookies / TLS context
    session.get("https://www.depop.com/")
    
    response = session.get(url, headers=headers)
    
    print(f"Status Code: {response.status_code}")
    try:
        data = response.json()
        saved_file = save_raw_json(data, "raw_products")
        print("Success! Sample keys / items:")
        if isinstance(data, dict):
            print(f"Keys: {list(data.keys())}")
        elif isinstance(data, list):
            print(f"Items count: {len(data)}")
    except Exception:
        print(f"Response Text: {response.text[:200]}")

if __name__ == "__main__":
    main()
