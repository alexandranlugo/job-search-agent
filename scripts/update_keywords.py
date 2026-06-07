import re

path = "ingestion/scrape_builtinnyc.py"
with open(path, "r") as f:
    content = f.read()

old = '''POSITIVE_KEYWORDS = [
    "data analyst", "product analyst", "insights analyst", "growth analyst",
    "business analyst", "analytics engineer", "bi analyst", "junior data scientist",
    "storytelling analyst", "marketing analyst", "decision analytics"
]'''

new = '''POSITIVE_KEYWORDS = [
    "data analyst", "product analyst", "insights analyst", "growth analyst",
    "business analyst", "analytics engineer", "bi analyst", "junior data scientist",
    "storytelling analyst", "marketing analyst", "decision analytics",
    "analyst", "analytics", "intelligence analyst", "data scientist",
    "data specialist", "data insights"
]'''

content = content.replace(old, new)
with open(path, "w") as f:
    f.write(content)
print("Keywords updated.")
