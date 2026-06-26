import os
from dotenv import load_dotenv
import anthropic

load_dotenv()

client = anthropic.Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))

def run_agent(query: str) -> str:
    response = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=1024,
        messages=[
            {"role": "user", "content": query}
        ]
    )
    return response.content[0].text

if __name__ == "__main__":
    result = run_agent("What are the key things hedge funds look for in financial news?")
    print(result)
