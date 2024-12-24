import asyncio
import random
import ssl
import json
import time
import uuid
import base64
import aiohttp
import requests
from datetime import datetime
from colorama import init, Fore, Style
from websockets_proxy import Proxy, proxy_connect

init(autoreset=True)

CHROME_USERAGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
]

EDGE_USERAGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36 Edg/122.0.2365.57",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36 Edg/121.0.2277.83",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36 Edg/120.0.2210.91"
]

HTTP_STATUS_CODES = {
    200: "OK",
    201: "Created",
    202: "Accepted",
    204: "No Content",
    400: "Bad Request",
    401: "Unauthorized",
    403: "Forbidden",
    404: "Not Found",
    500: "Internal Server Error",
    502: "Bad Gateway",
    503: "Service Unavailable",
    504: "Gateway Timeout"
}

def colorful_log(proxy, device_id, message_type, message_content, is_sent=False):
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
    color = Fore.GREEN if is_sent else Fore.BLUE
    action_color = Fore.YELLOW
    
    log_message = (
        f"{Fore.WHITE}[{timestamp}] "
        f"{Fore.MAGENTA}[Proxy: {proxy}] "
        f"{Fore.CYAN}[Device ID: {device_id}] "
        f"{action_color}[{message_type}] "
        f"{color}{message_content}"
    )
    
    print(log_message)

async def connect_to_wss(socks5_proxy, user_id):
    device_id = str(uuid.uuid5(uuid.NAMESPACE_DNS, socks5_proxy))
    
    random_user_agent = random.choice(CHROME_USERAGENTS) if hash(socks5_proxy) % 2 == 0 else random.choice(EDGE_USERAGENTS)

    colorful_log(
        proxy=socks5_proxy,  
        device_id=device_id, 
        message_type="INITIALIZATION", 
        message_content=f"User Agent: {random_user_agent}"
    )

    while True:
        try:
            await asyncio.sleep(random.randint(1, 10) / 10)
            custom_headers = {
                "User-Agent": random_user_agent,
                "Origin": "chrome-extension://lkbnfiajjmbhnfledhphioinpickokdi"
            }
            ssl_context = ssl.create_default_context()
            ssl_context.check_hostname = False
            ssl_context.verify_mode = ssl.CERT_NONE
            
            urilist = [
                #"wss://proxy.wynd.network:4444/",
                #"wss://proxy.wynd.network:4650/",
                "wss://proxy2.wynd.network:4444/",
                "wss://proxy2.wynd.network:4650/",
                #"wss://proxy3.wynd.network:4444/",
                #"wss://proxy3.wynd.network:4650/"
            ]
            
            uri = random.choice(urilist)
            server_hostname = "proxy.wynd.network"
            proxy = Proxy.from_url(socks5_proxy)
            
            async with proxy_connect(uri, proxy=proxy, ssl=ssl_context, server_hostname=server_hostname,
                                     extra_headers=custom_headers) as websocket:
                async def send_ping():
                    while True:
                        send_message = json.dumps(
                            {"id": str(uuid.uuid5(uuid.NAMESPACE_DNS, socks5_proxy)), 
                             "version": "1.0.0", 
                             "action": "PING", 
                             "data": {}})
                        
                        colorful_log(
                            proxy=socks5_proxy,  
                            device_id=device_id, 
                            message_type="SENDING PING", 
                            message_content=send_message,
                            is_sent=True
                        )
                        
                        await websocket.send(send_message)
                        await asyncio.sleep(5)

                await asyncio.sleep(1)
                asyncio.create_task(send_ping())

                while True:
                    response = await websocket.recv()
                    message = json.loads(response)
                    
                    colorful_log(
                        proxy=socks5_proxy, 
                        device_id=device_id, 
                        message_type="RECEIVED", 
                        message_content=json.dumps(message)
                    )

                    if message.get("action") == "AUTH":
                        auth_response = {
                            "id": message["id"],
                            "origin_action": "AUTH",
                            "result": {
                                "browser_id": device_id,
                                "user_id": user_id,
                                "user_agent": random_user_agent,
                                "timestamp": int(time.time()),
                                "device_type": "extension",
                                "version": "4.26.2",
                                "extension_id": "lkbnfiajjmbhnfledhphioinpickokdi"
                            }
                        }
                        
                        colorful_log(
                            proxy=socks5_proxy,  
                            device_id=device_id, 
                            message_type="AUTHENTICATING", 
                            message_content=json.dumps(auth_response),
                            is_sent=True
                        )
                        
                        await websocket.send(json.dumps(auth_response))
                    
                    elif message.get("action") == "HTTP_REQUEST":
                        request_data = message["data"]
                        
                        headers = {
                            "User-Agent": custom_headers["User-Agent"],
                            "Content-Type": "application/json; charset=utf-8"
                        }
                        
                        async with aiohttp.ClientSession() as session:
                            async with session.get(request_data["url"], headers=headers) as api_response:
                                content = await api_response.text()
                                encoded_body = base64.b64encode(content.encode()).decode()
                                
                                status_text = HTTP_STATUS_CODES.get(api_response.status, "")
                                
                                http_response = {
                                    "id": message["id"],
                                    "origin_action": "HTTP_REQUEST",
                                    "result": {
                                        "url": request_data["url"],
                                        "status": api_response.status,
                                        "status_text": status_text,
                                        "headers": dict(api_response.headers),
                                        "body": encoded_body
                                    }
                                }
                                
                                colorful_log(
                                    proxy=socks5_proxy,
                                    device_id=device_id,
                                    message_type="OPENING PING ACCESS",
                                    message_content=json.dumps(http_response),
                                    is_sent=True
                                )
                                
                                await websocket.send(json.dumps(http_response))

                    elif message.get("action") == "PONG":
                        pong_response = {"id": message["id"], "origin_action": "PONG"}
                        
                        colorful_log(
                            proxy=socks5_proxy, 
                            device_id=device_id, 
                            message_type="SENDING PONG", 
                            message_content=json.dumps(pong_response),
                            is_sent=True
                        )
                        
                        await websocket.send(json.dumps(pong_response))
        except Exception as e:
            colorful_log(
                proxy=socks5_proxy, 
                device_id=device_id, 
                message_type="ERROR", 
                message_content=str(e)
            )
            await asyncio.sleep(5)

import asyncio
import random
import ssl
import json
import time
import uuid
import base64
import aiohttp
import logging
from datetime import datetime
from colorama import init, Fore, Style
from websockets_proxy import Proxy, proxy_connect

init(autoreset=True)

CHROME_USERAGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
]

EDGE_USERAGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36 Edg/122.0.2365.57",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36 Edg/121.0.2277.83",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36 Edg/120.0.2210.91"
]

HTTP_STATUS_CODES = {
    200: "OK",
    201: "Created",
    202: "Accepted",
    204: "No Content",
    400: "Bad Request",
    401: "Unauthorized",
    403: "Forbidden",
    404: "Not Found",
    500: "Internal Server Error",
    502: "Bad Gateway",
    503: "Service Unavailable",
    504: "Gateway Timeout"
}

def colorful_log(proxy, device_id, message_type, message_content, is_sent=False):
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
    color = Fore.GREEN if is_sent else Fore.BLUE
    action_color = Fore.YELLOW
    
    log_message = (
        f"{Fore.WHITE}[{timestamp}] "
        f"{Fore.MAGENTA}[Proxy: {proxy}] "
        f"{Fore.CYAN}[Device ID: {device_id}] "
        f"{action_color}[{message_type}] "
        f"{color}{message_content}"
    )
    
    print(log_message)

async def connect_to_wss(socks5_proxy, user_id):
    device_id = str(uuid.uuid5(uuid.NAMESPACE_DNS, socks5_proxy))
    
    random_user_agent = random.choice(CHROME_USERAGENTS) if hash(socks5_proxy) % 2 == 0 else random.choice(EDGE_USERAGENTS)

    colorful_log(
        proxy=socks5_proxy,  
        device_id=device_id, 
        message_type="INITIALIZATION", 
        message_content=f"User Agent: {random_user_agent}"
    )

    while True:
        try:
            await asyncio.sleep(random.randint(1, 10) / 10)
            custom_headers = {
                "User-Agent": random_user_agent,
                "Origin": "chrome-extension://lkbnfiajjmbhnfledhphioinpickokdi"
            }
            ssl_context = ssl.create_default_context()
            ssl_context.check_hostname = False
            ssl_context.verify_mode = ssl.CERT_NONE
            
            urilist = [
                #"wss://proxy.wynd.network:4444/",
                #"wss://proxy.wynd.network:4650/",
                "wss://proxy2.wynd.network:4444/",
                "wss://proxy2.wynd.network:4650/",
                #"wss://proxy3.wynd.network:4444/",
                #"wss://proxy3.wynd.network:4650/"
            ]
            
            uri = random.choice(urilist)
            server_hostname = "proxy.wynd.network"
            proxy = Proxy.from_url(socks5_proxy)
            
            async with proxy_connect(uri, proxy=proxy, ssl=ssl_context, server_hostname=server_hostname,
                                     extra_headers=custom_headers) as websocket:
                async def send_ping():
                    while True:
                        send_message = json.dumps(
                            {"id": str(uuid.uuid5(uuid.NAMESPACE_DNS, socks5_proxy)), 
                             "version": "1.0.0", 
                             "action": "PING", 
                             "data": {}})
                        
                        colorful_log(
                            proxy=socks5_proxy,  
                            device_id=device_id, 
                            message_type="SENDING PING", 
                            message_content=send_message,
                            is_sent=True
                        )
                        
                        await websocket.send(send_message)
                        await asyncio.sleep(5)

                await asyncio.sleep(1)
                asyncio.create_task(send_ping())

                while True:
                    response = await websocket.recv()
                    message = json.loads(response)
                    
                    colorful_log(
                        proxy=socks5_proxy, 
                        device_id=device_id, 
                        message_type="RECEIVED", 
                        message_content=json.dumps(message)
                    )

                    if message.get("action") == "AUTH":
                        auth_response = {
                            "id": message["id"],
                            "origin_action": "AUTH",
                            "result": {
                                "browser_id": device_id,
                                "user_id": user_id,
                                "user_agent": random_user_agent,
                                "timestamp": int(time.time()),
                                "device_type": "extension",
                                "version": "4.26.2",
                                "extension_id": "lkbnfiajjmbhnfledhphioinpickokdi"
                            }
                        }
                        
                        colorful_log(
                            proxy=socks5_proxy,  
                            device_id=device_id, 
                            message_type="AUTHENTICATING", 
                            message_content=json.dumps(auth_response),
                            is_sent=True
                        )
                        
                        await websocket.send(json.dumps(auth_response))
                    
                    elif message.get("action") == "HTTP_REQUEST":
                        request_data = message["data"]
                        
                        headers = {
                            "User-Agent": custom_headers["User-Agent"],
                            "Content-Type": "application/json; charset=utf-8"
                        }
                        
                        async with aiohttp.ClientSession() as session:
                            async with session.get(request_data["url"], headers=headers) as api_response:
                                content = await api_response.text()
                                encoded_body = base64.b64encode(content.encode()).decode()
                                
                                status_text = HTTP_STATUS_CODES.get(api_response.status, "")
                                
                                http_response = {
                                    "id": message["id"],
                                    "origin_action": "HTTP_REQUEST",
                                    "result": {
                                        "url": request_data["url"],
                                        "status": api_response.status,
                                        "status_text": status_text,
                                        "headers": dict(api_response.headers),
                                        "body": encoded_body
                                    }
                                }
                                
                                colorful_log(
                                    proxy=socks5_proxy,
                                    device_id=device_id,
                                    message_type="OPENING PING ACCESS",
                                    message_content=json.dumps(http_response),
                                    is_sent=True
                                )
                                
                                await websocket.send(json.dumps(http_response))

                    elif message.get("action") == "PONG":
                        pong_response = {"id": message["id"], "origin_action": "PONG"}
                        
                        colorful_log(
                            proxy=socks5_proxy, 
                            device_id=device_id, 
                            message_type="SENDING PONG", 
                            message_content=json.dumps(pong_response),
                            is_sent=True
                        )
                        
                        await websocket.send(json.dumps(pong_response))
        except Exception as e:
            colorful_log(
                proxy=socks5_proxy, 
                device_id=device_id, 
                message_type="ERROR", 
                message_content=str(e)
            )
            await asyncio.sleep(5)

def fetch_proxies():
    """Fetches proxies from the API and saves them to 'auto_proxies.txt'."""
    api_url = "https://api.proxyscrape.com/v4/free-proxy-list/get?request=display_proxies&proxy_format=protocolipport&format=text"
    try:
        response = requests.get(api_url, stream=True)
        if response.status_code == 200:
            proxies = response.text.strip().splitlines()
            if proxies:
                with open('auto_proxies.txt', 'w') as f:
                    f.writelines([proxy + '\n' for proxy in proxies])
                print(f"Fetched and saved {len(proxies)} proxies to 'auto_proxies.txt'.")
            else:
                print("No proxies found from the API.")
                return False
        else:
            print(f"Failed to fetch proxies. Status code: {response.status_code}")
            return False
    except Exception as e:
        print(f"Error fetching proxies: {e}")
        return False
    return True

async def main():
    _user_id = "2p4GgmhEwvn4B8NPpwyxHnAbzjk"
    if not fetch_proxies():
        print("No proxies available. Exiting script.")
        return

    try:
        with open('auto_proxies.txt', 'r') as file:
            auto_proxy_list = file.read().splitlines()
            if not auto_proxy_list:
                print("No proxies found in 'auto_proxies.txt'. Exiting script.")
                return
            print(f"Proxies read from file: {auto_proxy_list}")
    except FileNotFoundError:
        print("Error: 'auto_proxies.txt' file not found.")
        return

    tasks = [asyncio.ensure_future(connect_to_wss(i, _user_id)) for i in auto_proxy_list]
    await asyncio.gather(*tasks)

if __name__ == '__main__':
    asyncio.run(main())
