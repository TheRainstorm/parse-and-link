import requests

class Jellyfin:
    def __init__(self, jellyfin_url, api_key):
        self.jellyfin_url = jellyfin_url
        self.api_key = api_key
        self.headers = {
            "X-Emby-Authorization": f"MediaBrowser Client=\"pal\", Device=\"pal\", DeviceId=\"pal\", Version=\"1.0.0\", Token=\"{api_key}\"",
        }
        
    def refresh(self):
        api_endpoint = "/Library/Refresh"
        api_url = f"{self.jellyfin_url}{api_endpoint}"

        response = requests.post(api_url, headers=self.headers)
        return response.status_code
