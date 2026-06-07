"""
Tests common Greenhouse slug variations for each company.
"""
import urllib.request, urllib.error, time

COMPANIES = {
    "New York Times":     ["nytimes", "the-new-york-times", "newyorktimes", "nyt"],
    "Warner Music Group": ["warnermusicgroup", "warner-music-group", "wmg", "warnermusic"],
    "Sony Music":         ["sonymusic", "sony-music", "sonymusicentertainment", "sonybmg"],
    "AMC Networks":       ["amcnetworks", "amc-networks", "amcnetwork"],
    "SoundCloud":         ["soundcloud", "sound-cloud"],
    "SiriusXM":           ["siriusxm", "sirius-xm", "pandora", "siriusxmpandora"],
    "The Athletic":       ["theathletic", "the-athletic"],
    "Substack":           ["substack"],
    "Roc Nation":         ["rocnation", "roc-nation"],
    "Luminate":           ["luminate", "luminatedata", "luminate-data"],
    "Spotify":            ["spotify"],
}

for company, slugs in COMPANIES.items():
    for slug in slugs:
        url = f"https://boards-api.greenhouse.io/v1/boards/{slug}/jobs"
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
            with urllib.request.urlopen(req, timeout=8) as r:
                import json
                data = json.loads(r.read())
                count = len(data.get("jobs", []))
                print(f"  FOUND {company}: slug={slug} ({count} jobs)")
                break
        except urllib.error.HTTPError:
            pass
        except Exception as e:
            pass
        time.sleep(0.3)
    else:
        print(f"  NOT FOUND: {company}")
