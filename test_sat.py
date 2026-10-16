import datetime
import requests

now = datetime.datetime.now(datetime.timezone.utc)
print("Current UTC:", now)

for m in range(0, 120, 10):
    t = now - datetime.timedelta(minutes=m)
    # round to 10 min
    minute = (t.minute // 10) * 10
    iso = t.replace(minute=minute, second=0, microsecond=0).strftime("%Y-%m-%dT%H:%M:00Z")

    url_vs = f"https://satellite.bmkg.go.id/api22/tile/4/13/7.png?tiletype=himawari9&modelname=himawari9hires&param=VS&baserun={iso}"
    url_eh = f"https://satellite.bmkg.go.id/api22/tile/4/13/7.png?tiletype=himawari9&modelname=himawari9&param=EH&baserun={iso}"

    headers = {"Referer": "https://cuaca.bmkg.go.id/"}
    r_vs = requests.get(url_vs, headers=headers)
    r_eh = requests.get(url_eh, headers=headers)
    print(f"baserun: {iso} -> VS status: {r_vs.status_code}, EH status: {r_eh.status_code}")
