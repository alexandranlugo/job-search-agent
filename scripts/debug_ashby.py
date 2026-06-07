import urllib.request, json

companies = {
    "New York Times":     "nytimes",
    "Warner Music Group": "warnermusicgroup",
    "AMC Networks":       "amcnetworks",
    "SoundCloud":         "soundcloud",
    "Roc Nation":         "rocnation",
}

for name, slug in companies.items():
    try:
        api_url = "https://jobs.ashbyhq.com/api/non-user-graphql"
        payload = json.dumps({
            "operationName": "ApiJobBoardWithTeams",
            "variables": {"organizationHostedJobsPageName": slug},
            "query": "query ApiJobBoardWithTeams($organizationHostedJobsPageName: String!) { jobBoard: publishedJobBoard(organizationHostedJobsPageName: $organizationHostedJobsPageName) { jobPostings { id title locationName } } }"
        }).encode()

        req = urllib.request.Request(
            api_url,
            data=payload,
            headers={"Content-Type": "application/json", "User-Agent": "Mozilla/5.0"}
        )
        with urllib.request.urlopen(req, timeout=15) as r:
            data = json.loads(r.read())

        jobs = data.get("data", {}).get("jobBoard", {}).get("jobPostings", [])
        print(f"{name}: {len(jobs)} jobs")
        for j in jobs[:5]:
            print(f"  - {j['title']} ({j.get('locationName','')})")
    except Exception as e:
        print(f"{name}: ERROR — {e}")
