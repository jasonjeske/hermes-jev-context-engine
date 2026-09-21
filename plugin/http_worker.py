"""Isolated bounded HTTP worker. No diagnostic output or retries."""
import json
import sys
import urllib.request

class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self,*args,**kwargs): return None

def main():
    data=json.loads(sys.stdin.buffer.read(131072))
    if data['url']!='https://openrouter.ai/api/alpha/decisions': return 2
    opener=urllib.request.build_opener(urllib.request.ProxyHandler({}),NoRedirect())
    request=urllib.request.Request(data['url'],data=data['body'].encode(),headers=data['headers'],method='POST')
    with opener.open(request,timeout=data['timeout']) as response:
        raw=response.read(262145)
        if response.status!=200 or len(raw)>262144: return 2
        sys.stdout.buffer.write(raw)
    return 0

if __name__=='__main__':
    try: code=main()
    except Exception: code=2
    sys.exit(code)
