"""Rebuild assets/json/resume.json (the /cv/ page) from the canonical CV LaTeX in _scripts/cv_main.tex.

_scripts/cv_main.tex is CV artifact 76b72bf4, version 9c267107-0b2d-4525-8e98-d73b1a981181.
CV-derived strings are extracted from the .tex, never retyped. Factual items that exist only on the old
web page (course lists, the 2018-19 Rutgers CS post-baccalaureate, award links, Iunu team sentence) are kept.
Usage, from the repo root: python _scripts/cv_to_resume.py _scripts/cv_main.tex assets/json/resume.json
then: npx prettier --write assets/json/resume.json
"""
import json, re, sys

MONTHS = {m: i + 1 for i, m in enumerate("January February March April May June July August September October November December".split())}


def clean(s):
    s = re.sub(r"(?<!\\)%.*", "", s)
    s = s.replace(r"\me", "K. A. Reid").replace("~", " ").replace("``", "\u201c").replace("''", "\u201d")
    s = re.sub(r"\\href\{[^}]*\}\{([^}]*)\}", r"\1", s)
    s = re.sub(r"\\(emph|textbf|textit|sl)\{([^}]*)\}", r"\2", s)
    s = s.replace("--", "\u2013").replace(r"\&", "&")
    return re.sub(r"\s+", " ", s).strip()


def date(s):  # "September 2025" -> "2025-09"; "2017" -> "2017"; "" -> ""
    s = s.strip()
    if s.lower() == "present":
        return ""  # theme renders an empty end date as "Present"
    m = re.match(r"([A-Z][a-z]+) (\d{4})$", s)
    return f"{m.group(2)}-{MONTHS[m.group(1)]:02d}" if m else s


def section(tex, name):
    return re.search(r"\\resheading\{" + name + r"\}(.*?)(?=\\resheading|\\end\{document\})", tex, re.S).group(1)


def items(block, env):
    return [clean(x) for b in re.findall(r"\\begin\{" + env + r"\}(.*?)\\end\{" + env + r"\}", block, re.S) for x in b.split(r"\item")[1:]]


tex = open(sys.argv[1]).read()
old = json.load(open(sys.argv[2]))
interests = clean(section(tex, "RESEARCH INTERESTS").replace(r"\par\vspace{4pt}\noindent", ""))

# Experience entries: \entry{org}{place}{title}{dates} followed by a tight list
work = []
for sec in ("RESEARCH EXPERIENCE", "INDUSTRY EXPERIENCE"):
    for org, place, title, dates, body in re.findall(r"\\entry\{(.*?)\}\{(.*?)\}\s*\{(.*?)\}\{(.*?)\}(.*?)(?=\\entry|\Z)", section(tex, sec), re.S):
        start, _, end = (clean(dates) + " \u2013 ").partition("\u2013")
        work.append({"name": clean(org), "position": clean(title), "location": clean(place), "url": "",
                     "startDate": date(start), "endDate": date(end.strip(" \u2013")), "summary": "", "highlights": items(body, "tight")})
old_urls = {w["name"].split(",")[0]: w["url"] for w in old["work"]}
for w in work:  # keep the old page's employer links where the employer matches
    for k, u in old_urls.items():
        if k.split()[0] in w["name"] and "Johns Hopkins" not in w["name"]:
            w["url"] = u
    if w["name"].startswith("Children's National"):
        w["url"] = next(o["url"] for o in old["work"] if "Children's National" in o["name"])
    if w["name"].endswith("Department of Epidemiology"):
        w["url"] = "https://pearlhivmodel.org/index.html"
    if w["name"] == "Iunu":  # user-written sentence from the old page, not on the CV
        w["summary"] = "First Data Scientist at a small company. Built the team up to 6 data scientists and engineers."

# Publications: \subhead{...} then pubs items; authors before the opening quote, title inside, venue after
pubs = []
pub_block = section(tex, "PUBLICATIONS")
for head, body in re.findall(r"\\subhead\{(.*?)\}(.*?)(?=\\subhead|\Z)", pub_block, re.S):
    raw_items = re.findall(r"\\begin\{pubs\}(.*?)\\end\{pubs\}", body, re.S)[0].split(r"\item")[1:]
    for raw in raw_items:
        url = (re.findall(r"\\href\{([^}]*)\}", raw) or [""])[0]
        c = clean(raw)
        doi = re.search(r"doi: ?(10\.\S+?)\.?$", c)
        url = url or (f"https://doi.org/{doi.group(1)}" if doi else "")
        authors, title, venue = re.match(r"(.*?)[\u201c\"](.*?)[\u201d\"](.*)", c).groups()
        venue = re.sub(r"\s*(Preprint: )?doi: ?10\.\S+$", "", venue)  # DOI is already the link
        year = re.search(r"(20\d\d)", venue) or re.search(r"/(20\d\d)\.\d\d\.", url)  # in-press papers: preprint posting year from the bioRxiv/medRxiv DOI
        pubs.append({"name": title.strip().rstrip(",."), "publisher": venue.strip(" ,."), "releaseDate": year.group(1) if year else "",
                     "url": url, "summary": authors.strip(" ,.")})

# Education: \edu{inst}{place}{degree}{dates}
education = []
for inst, place, deg, dates in re.findall(r"\\edu\{(.*?)\}\{(.*?)\}\s*\{(.*?)\}\{(.*?)\}", section(tex, "EDUCATION"), re.S):
    start, _, end = (clean(dates) + " \u2013 ").partition("\u2013")
    study, _, area = clean(deg).partition(", ")
    education.append({"institution": clean(inst), "location": clean(place), "url": "", "area": area, "studyType": study,
                      "startDate": date(start), "endDate": date(end.strip(" \u2013")), "score": "", "courses": []})
for e in education:  # keep the old page's program links and course lists
    for o in old["education"]:
        if o["institution"] == e["institution"] and (o["area"].split()[0] in e["area"]):
            e["url"], e["courses"] = o["url"], [c.replace("Combinatoricss", "Combinatorics") for c in o["courses"]]
education[0]["endDate"] = ""  # theme's date badge overflows on "expected 2030"; renders "Present" (the PDF keeps the expected year)
cs_postbacc = next(o for o in old["education"] if o["area"] == "Computer Science")
cs_postbacc = dict(cs_postbacc, location="New Brunswick, NJ", studyType="Post-baccalaureate")
education.insert(-1, cs_postbacc)  # 2018-19, before the 2013-17 B.A.

# Honors: keep the old page's award entries (links, summaries) and add those only on the CV
honors = items(section(tex, "HONORS AND AWARDS"), "tight")
awards = []
for h in honors:
    title, *rest = [x.strip() for x in h.split(",")]
    match = next((o for o in old["awards"] if o["title"].split()[0:2] == title.split()[0:2]), None)
    if match:
        awards.append(dict(match, summary=match["summary"].rstrip("'")))
    else:
        awards.append({"title": title, "date": rest[-1], "awarder": ", ".join(rest[:-1]), "url": "", "summary": ""})

skills = [{"name": clean(n), "icon": "fa-solid fa-hashtag", "keywords": [k.strip() for k in clean(v).split(",")]}
          for n, v in re.findall(r"\\textbf\{(.*?)\}\\quad (.*?)(?:\\\\\[2pt\]|\n\n|\\end)", section(tex, "TECHNICAL SKILLS"), re.S)]

site_url = re.search(r"\\href\{(https://[^}]*\.github\.io)\}", tex).group(1)  # ponytail: assumes a github.io address; change the pattern if the site moves to its own domain
basics = dict(old["basics"], label="Ph.D. Student in Computer Science, Johns Hopkins University", summary=interests, url=site_url)
new = {"basics": basics, "education": education, "publications": pubs, "work": work, "awards": awards, "skills": skills,
       "languages": old["languages"], "certificates": [], "interests": [], "references": [], "projects": []}
json.dump(new, open(sys.argv[2], "w"), indent=2, ensure_ascii=False)
open(sys.argv[2], "a").write("\n")
