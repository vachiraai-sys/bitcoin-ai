
import requests

def send_line_msg(token, message):
    """
    Send a message to LINE Notify
    """
    url = "https://notify-api.line.me/api/notify"
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/x-www-form-urlencoded"
    }
    payload = {
        "message": message
    }
    
    try:
        response = requests.post(url, headers=headers, data=payload, timeout=5)
        response.raise_for_status()
        return response.status_code == 200
    except requests.exceptions.ConnectionError:
        print("Warning: Could not connect to LINE Notify API (Check internet connection or DNS).")
        return False
    except Exception as e:
        print(f"Error sending LINE Notify: {e}")
        return False
