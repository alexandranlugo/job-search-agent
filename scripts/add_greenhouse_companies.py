"""
Adds known Greenhouse API slugs for companies in portals.yml that are missing them.
Run once to patch the scraper's company list.
"""

GREENHOUSE_SLUGS = {
    "New York Times":           "nytimes",
    "Warner Music Group":       "warnermusicgroup",
    "Sony Music Entertainment": "sonymusic",
    "AMC Networks":             "amcnetworks",
    "SoundCloud":               "soundcloud",
    "Pandora / SiriusXM":       "siriusxm",
    "The Athletic (NYT)":       "theathletic",
    "Substack":                 "substack",
    "Luminate":                 "luminate",
    "Roc Nation":               "rocnation",
}

ASHBY_SLUGS = {
    "Chartmetric":  "chartmetric",
    "Qloo":         "qloo",
    "NewsWhip":     "newswhip",
    "Audiomack":    "audiomack",
}

LEVER_SLUGS = {
    "Genius":       "genius",
    "Bandsintown":  "bandsintown",
    "Letterboxd":   "letterboxd",
}

print("Greenhouse companies to try:")
for name, slug in GREENHOUSE_SLUGS.items():
    print(f"  {name}: https://boards-api.greenhouse.io/v1/boards/{slug}/jobs")

print("\nAshby companies to try:")
for name, slug in ASHBY_SLUGS.items():
    print(f"  {name}: https://jobs.ashbyhq.com/{slug}")

print("\nLever companies to try:")
for name, slug in LEVER_SLUGS.items():
    print(f"  {name}: https://api.lever.co/v0/postings/{slug}?mode=json")
