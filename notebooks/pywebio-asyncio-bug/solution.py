from pywebio import start_server, output
import asyncio
import requests

def request():
    try:
        ret = requests.get("http://www.baidu.com")
        print(ret.status_code)
        ret = requests.get("123.123.123.123")
        print(ret.status_code)
    except Exception as e:
        print("my error")
        print(str(e))
        return str(e)

async def solution_httpx():
    e = await asyncio.to_thread(request)
    output.put_text(e)
    # await asyncio.get_running_loop().run_in_executor(None, request())


start_server(solution_httpx, 8081)