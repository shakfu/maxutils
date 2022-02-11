import os
import webloc

links = []
for f in os.listdir("links"):
    if f == '.DS_Store':
        continue
    try:
        links.append((f.strip(".webloc"), webloc.read(f)))
    except:
        print(f"FAILED: {f}")

with open("out.md", "w") as f:
    for txt, link in links:
        f.write(f"[{txt}]({link})\n")
