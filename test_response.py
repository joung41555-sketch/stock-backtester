import urllib.request

try:
    response = urllib.request.urlopen("http://localhost:8501", timeout=5)
    html = response.read().decode('utf-8')
    print("STATUS CODE: 200")
    print("HTML Length:", len(html))
    if "Traceback" in html or "Exception" in html or "Error" in html:
        print("DETECTED ERROR/EXCEPTION IN HTML RESPONSE:")
        lines = html.split("\n")
        for line in lines:
            if "Traceback" in line or "Error" in line or "Exception" in line:
                print(line[:200])
    else:
        print("No Python Exception strings found in HTML root.")
except Exception as e:
    print("REQUEST FAILED:", e)
