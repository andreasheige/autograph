import json
import urllib.request
from typing import Dict, Any
from config.settings import Config

class Synthesizer:
    def __init__(self, model_name=None, api_url=None):
        # Use provided model/url or fallback to Config
        self.model_name = model_name or Config.MODEL_NAME
        self.api_url = api_url or Config.OLLAMA_API_URL

    def synthesize(self, text):
        """
        Sends text to Ollama and expects a JSON response.
        """
        prompt = (
            f"Extract entities and relations from this text. "
            f"Return ONLY JSON. For the 'entities' list, use simple strings (e.g., ['part1', 'arg2']). "
            f"Text: {text}"
        )
        
        payload = {
            "model": self.model_name, 
            "prompt": prompt, 
            "stream": False, 
            "format": "json"
        }
        
        try:
            data = json.dumps(payload).encode("utf-8")
            req = urllib.request.Request(
                self.api_url, 
                data=data, 
                headers={"Content-Type": "application/json"}
            )
            with urllib.request.urlopen(req) as response:
                res_body = response.read().decode("utf-8")
                response_json = json.loads(res_body)
                
                # The Ollama API returns the model response in the "response" field
                raw_response = response_json.get("response", "{}")
                
                # We return the parsed JSON string to keep it consistent with previous implementation
                return json.dumps(json.loads(raw_response))
        except Exception as e:
            return json.dumps({"error": str(e)})

    def synthesize_session(self, prompt_data: Dict[str, Any]) -> str:
        """
        Specialized synthesis for the Session Observer Agent.
        Converts a raw log and commit hash into a first-person engineering narrative.
        """
        prompt = (
            f"Review the following raw engineering logs and a commit hash. "
            f"Synthesize these into a professional, high-fidelity 'Engineering Narrative' written in the first person. "
            f"Include sections for: Achievements, Challenges/Blockers, and Next Steps. "
            f"Ignore trivial command output noise. Focus on architectural reasoning and technical decisions. "
            f"Raw Logs: {prompt_data.get('session_raw_log', '')} "
            f"Commit Hash: {prompt_data.get('trigger_commit', '')}"
        )
        
        payload = {
            "model": self.model_name, 
            "prompt": prompt, 
            "stream": False, 
            "format": "text"
        }
        
        try:
            data = json.dumps(payload).encode("utf-8")
            req = urllib.request.Request(
                self.api_url, 
                data=data, 
                headers={"Content-Type": "application/json"}
            )
            with urllib.request.urlopen(req) as response:
                res_body = response.read().decode("utf-8")
                response_json = json.loads(res_body)
                return response_json.get("response", "No narrative produced.")
        except Exception as e:
            return f"Error during session synthesis: {str(e)}"

    def synthesize_for_journal(self, text):
        """
        Specialized synthesis for the Daily Summary Agent.
        """
        prompt = (
            f"You are a personal biographer. Review these events from the last 24 hours "
            f"and write a beautiful, concise, and engaging daily journal entry. "
            f"Mention the weather. Format it for Obsidian with headers and bullet points. "
            f"Text: {text}"
        )
        
        payload = {
            "model": self.model_name, 
            "prompt": prompt, 
            "stream": False, 
            "format": "json"
        }
        
        try:
            data = json.dumps(payload).encode("utf-8")
            req = urllib.request.Request(
                self.api_url, 
                data=data, 
                headers={"Content-Type": "application/json"}
            )
            with urllib.request.urlopen(req) as response:
                res_body = response.read().decode("utf-8")
                response_json = json.loads(res_body)
                raw_response = response_json.get("response", "{}")
                return json.dumps({"journal": json.loads(raw_response)})
        except Exception as e:
            return json.dumps({"error": str(e)})
