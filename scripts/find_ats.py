"""
Checks which ATS each company uses by probing common endpoints.
"""
import urllib.request, urllib.error, time

COMPANIES = {
    "New York Times":     ["nytimes", "the-new-york-times", "nyt", "newyorktimes"],
    "Warner Music Group": ["warnermusicgroup", "wmg", "warnermusic", "warner-music-group"],
    "AMC Networks":       ["amcnetworks", "amc-networks"],
    "SoundCloud":         ["soundcloud"],
    "SiriusXM":           ["siriusxm", "pandora", "siriusxmpandora"],
    "The Athletic":       ["theathletic", "the-athletic"],
    "Substack":           ["substack"],
    "Roc Nation":         ["rocnation", "roc-nation"],
}

def probe(url):
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=8) as r:
            return r.status
    except urllib.error.HTTPError as e:
        return e.code
    except:
        return None

for company, slugs in COMPANIES.items():
    found = False
    for slug in slugs:
        results = {
            "Greenhouse": f"https://boards-api.greenhouse.io/v1/boards/{slug}/jobs",
            "Lever":      f"https://api.lever.co/v0/postings/{slug}?mode=json",
            "Ashby":      f"https://jobs.ashbyhq.com/{slug}",
        }
        for ats, url in results.items():
            code = probe(url)
            if code == 200:
                print(f"  FOUND {company}: {ats} slug={slug}")
                found = True
                break
            time.sleep(0.2)
        if found:
            break
    if not found:
        print(f"  NOT FOUND: {company} — likely Workday, custom ATS, or LinkedIn")
