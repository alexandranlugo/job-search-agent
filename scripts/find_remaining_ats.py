import urllib.request, urllib.error, time, json

COMPANIES = {
    "ASCAP":            ["ascap"],
    "Activate Consulting": ["activateconsulting", "activate-consulting", "activate"],
    "Adelaide Metrics": ["adelaidemetrics", "adelaide-metrics", "adelaide"],
    "Luminary":         ["luminary", "luminarypodcasts"],
    "Letterboxd":       ["letterboxd"],
    "Bandsintown":      ["bandsintown"],
    "NewsWhip":         ["newswhip"],
    "Pitchfork":        ["condenast", "conde-nast", "pitchfork"],
    "Luminate":         ["luminate", "luminatedata"],
}

def probe(url):
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=8) as r:
            data = r.read()
            if b"jobs" in data.lower() or b"posting" in data.lower():
                return r.status, len(data)
            return r.status, 0
    except urllib.error.HTTPError as e:
        return e.code, 0
    except:
        return None, 0

for company, slugs in COMPANIES.items():
    found = False
    for slug in slugs:
        for ats, url_template in [
            ("Greenhouse", f"https://boards-api.greenhouse.io/v1/boards/{slug}/jobs"),
            ("Lever",      f"https://api.lever.co/v0/postings/{slug}?mode=json"),
            ("Ashby",      f"https://jobs.ashbyhq.com/api/non-user-graphql"),
        ]:
            if ats == "Ashby":
                try:
                    payload = json.dumps({
                        "operationName": "ApiJobBoardWithTeams",
                        "variables": {"organizationHostedJobsPageName": slug},
                        "query": "query ApiJobBoardWithTeams($organizationHostedJobsPageName: String!) { jobBoard: publishedJobBoard(organizationHostedJobsPageName: $organizationHostedJobsPageName) { jobPostings { id title } } }"
                    }).encode()
                    req = urllib.request.Request(
                        url_template, data=payload,
                        headers={"Content-Type": "application/json", "User-Agent": "Mozilla/5.0"}
                    )
                    with urllib.request.urlopen(req, timeout=8) as r:
                        data = json.loads(r.read())
                    jobs = data.get("data", {}).get("jobBoard", {}).get("jobPostings", [])
                    if jobs is not None:
                        print(f"  FOUND {company}: Ashby slug={slug} ({len(jobs)} jobs)")
                        found = True
                        break
                except:
                    pass
            else:
                code, size = probe(url_template)
                if code == 200 and size > 100:
                    print(f"  FOUND {company}: {ats} slug={slug}")
                    found = True
                    break
            time.sleep(0.2)
        if found:
            break
    if not found:
        print(f"  NOT FOUND: {company}")
