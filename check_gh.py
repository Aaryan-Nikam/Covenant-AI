import urllib.request
import json
url = "https://api.github.com/repos/Aaryan-Nikam/Ironpass/actions/runs"
req = urllib.request.Request(url, headers={"Accept": "application/vnd.github.v3+json"})
with urllib.request.urlopen(req) as response:
    data = json.loads(response.read().decode())
    runs = data.get("workflow_runs", [])[:2]
    for r in runs:
        print(f"[{r.get('status')}] {r.get('conclusion')} | {r.get('name')}")
        try:
            print(f"Message: {r.get('head_commit',{}).get('message')}")
        except:
            pass
