from curl_cffi import requests


#This is a test request directed at groups/categories endpoint

def main():
    url = "https://webapi.depop.com/presentation/api/v1/attributes/groups/"
    
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
        print("Success! Sample data:")
        print(data[:2] if isinstance(data, list) else data)
    except Exception:
        print(f"Response Text: {response.text[:200]}")

if __name__ == "__main__":
    main()
