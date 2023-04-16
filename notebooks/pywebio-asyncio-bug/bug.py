import httpx
import aiohttp
from pywebio import start_server
from tornado.httpclient import AsyncHTTPClient

async def test_tornado():
    c = AsyncHTTPClient()
    try:
        resp = await c.fetch("123.123.123.123")
    except Exception as e:
        print("error 1234")
        print(str(e))

async def test_httpx():
    try:
        async with httpx.AsyncClient() as c:
            await c.get("http://www.baidu.com")
    except Exception as e:
        print(str(e))

async def test_aiohttp():
    try:
        async with aiohttp.ClientSession(timeout=1) as session:
            async with session.get("http://www.baidu.com", timeout=1) as response:
                print(response.status)
                print(response.content)
    except:
        print("catch error")
        raise


start_server([test_tornado, test_httpx, test_aiohttp], 8080)