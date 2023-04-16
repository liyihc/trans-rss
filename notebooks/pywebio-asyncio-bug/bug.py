import asyncio
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
        import httpx
        async with httpx.AsyncClient() as c:
            await c.get("http://www.baidu.com")
    except Exception as e:
        print(str(e))

async def test_aiohttp():
    try:
        import aiohttp
        async with aiohttp.ClientSession(timeout=1) as session:
            async with session.get("http://www.baidu.com", timeout=1) as response:
                print(response.status)
                print(response.content)
    except:
        print("catch error")
        raise

async def a_raise_error():
    raise ValueError("123")

async def test_async():
    try:
        await a_raise_error()
    except:
        print("catch error")
        raise

def raise_error():
    raise ValueError("123")

async def test_run_in_thread():
    try:
        await asyncio.to_thread(raise_error)
    except:
        print("catch error")
        raise
    

start_server([test_tornado, test_httpx, test_aiohttp, test_async, test_run_in_thread], 8080)