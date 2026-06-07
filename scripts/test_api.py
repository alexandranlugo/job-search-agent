import os, sys
from dotenv import load_dotenv

load_dotenv(os.path.join(os.path.dirname(__file__), "..", ".env"))

api_key = os.getenv("ANTHROPIC_API_KEY")

if not api_key or api_key == "your_api_key_here":
    print("ERROR: ANTHROPIC_API_KEY not set in .env")
    print("Edit job-search-agent/.env and replace 'your_api_key_here' with your real key.")
    sys.exit(1)

try:
    import anthropic
except ImportError:
    print("ERROR: anthropic package not installed. Run: pip install -r requirements.txt")
    sys.exit(1)

client = anthropic.Anthropic(api_key=api_key)
print("Sending test message...")

response = client.messages.create(
    model="claude-sonnet-4-6",
    max_tokens=64,
    messages=[{"role": "user", "content": "Reply with exactly: API connection confirmed."}]
)

print(response.content[0].text)
print("\nAll good. Ready for Phase 2.")
