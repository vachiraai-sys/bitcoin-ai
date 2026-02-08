
import requests
import json
import time
import streamlit as st

class LineMessagingService:
    def __init__(self):
        # Load configuration from secrets.toml
        try:
            self.list_api = st.secrets["line_api_list"]
        except Exception as e:
            st.error(f"Error loading LINE API configuration: {e}")
            print(f"Error loading LINE API configuration: {e}")
            self.list_api = []

        self.current_index = 0
        self.api_url = "https://api.line.me/v2/bot/message/push"

    def send_message(self, message, retry_count=0):
        """
        Sends a message using the current token.
        Rotates token and retries if 429 (Rate Limit) is encountered.
        """
        if not message:
            return False

        # Max retries to prevent infinite loops (e.g. if all tokens are limited)
        if retry_count >= len(self.list_api):
            print("All tokens rate limited or failed.")
            return False

        config = self.list_api[self.current_index]
        token = config['token']
        user_id = config['user_id']
        
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {token}"
        }
        
        payload = {
            "to": user_id,
            "messages": [
                {
                    "type": "text",
                    "text": message
                }
            ]
        }
        
        try:
            response = requests.post(self.api_url, headers=headers, data=json.dumps(payload))
            
            if response.status_code == 200:
                # Success
                return True
                
            elif response.status_code == 429:
                # Rate Limit -> Rotate Token
                print(f"Rate Limit (429) on token index {self.current_index}. Rotating...")
                self._rotate_token()
                # Recursive retry with next token
                return self.send_message(message, retry_count + 1)
                
            else:
                # Other errors
                print(f"LINE API Error: {response.status_code} - {response.text}")
                return False
                
        except Exception as e:
            print(f"Exception sending LINE message: {e}")
            return False

    def _rotate_token(self):
        """Increments index, looping back to 0 if at end."""
        self.current_index = (self.current_index + 1) % len(self.list_api)
        print(f"Switched to token index: {self.current_index}")
