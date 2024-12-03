import ssl
import json
import time
import uuid
import random
import shutil
import asyncio
import requests
import threading
from loguru import logger
from fake_useragent import UserAgent
from websockets_proxy import Proxy, proxy_connect

async def connect_to_wss(socks5_proxy, user_id):
    user_agent = UserAgent(os=['windows', 'macos', 'linux'], browsers='chrome')
    random_user_agent = user_agent.random
    device_id = str(uuid.uuid3(uuid.NAMESPACE_DNS, socks5_proxy))
    logger.info(device_id)
    while True:
        try:
            await asyncio.sleep(random.randint(1, 10) / 10)
            custom_headers = {
                "User-Agent": random_user_agent,
            }
            ssl_context = ssl.create_default_context()
            ssl_context.check_hostname = False
            ssl_context.verify_mode = ssl.CERT_NONE
            urilist = ["wss://proxy2.wynd.network:4444/", "wss://proxy2.wynd.network:4650/"]
            uri = random.choice(urilist)
            server_hostname = "proxy2.wynd.network"
            proxy = Proxy.from_url(socks5_proxy)
            async with proxy_connect(uri, proxy=proxy, ssl=ssl_context, server_hostname=server_hostname,
                                     extra_headers=custom_headers) as websocket:
                async def send_ping():
                    while True:
                        send_message = json.dumps({
                            "id": str(uuid.uuid4()), "version": "1.0.0", "action": "PING", "data": {}
                        })
                        logger.debug(send_message)
                        await websocket.send(send_message)
                        await asyncio.sleep(4)

                await asyncio.sleep(1)
                asyncio.create_task(send_ping())

                while True:
                    response = await websocket.recv()
                    message = json.loads(response)
                    logger.info(message)
                    if message.get("action") == "AUTH":
                        auth_response = {
                            "id": message["id"],
                            "origin_action": "AUTH",
                            "result": {
                                "browser_id": device_id,
                                "user_id": user_id,
                                "user_agent": custom_headers['User-Agent'],
                                "timestamp": int(time.time()),
                                "device_type": "desktop",
                                "version": "4.29.0",
                            }
                        }
                        logger.debug(auth_response)
                        await websocket.send(json.dumps(auth_response))

                    elif message.get("action") == "PONG":
                        pong_response = {"id": message["id"], "origin_action": "PONG"}
                        logger.debug(pong_response)
                        await websocket.send(json.dumps(pong_response))
        except Exception as e:
            proxy_to_remove = socks5_proxy
            with open('auto_proxies.txt', 'r') as file:
                lines = file.readlines()
            updated_lines = [line for line in lines if line.strip() != proxy_to_remove]
            with open('auto_proxies.txt', 'w') as file:
                file.writelines(updated_lines)
            print(f"Proxy '{proxy_to_remove}' has been removed from the file.")

total_proxies_fetched = 0
lock = threading.Lock()

def fetch_proxies_from_multiple_pages(start_page=1, end_page=15):
    global total_proxies_fetched

    base_url = "https://proxylist.geonode.com/api/proxy-list?limit=500&page={}&sort_by=lastChecked&sort_type=desc"
    
    all_proxies = set() 
    
    for page_num in range(start_page, end_page + 1):
        url = base_url.format(page_num)
        
        try:
            response = requests.get(url)
            response.raise_for_status()
            data = response.json()
            
            for proxy in data["data"]:
                ip = proxy["ip"]
                port = proxy["port"]
                protocols = proxy["protocols"]
                
                for protocol in protocols:
                    proxy_str = f"{protocol}://{ip}:{port}"
                    all_proxies.add(proxy_str)
        
        except requests.RequestException as e:
            print(f"Error fetching data from page {page_num}: {e}")
    
    with lock:
        total_proxies_fetched += len(all_proxies)
    
    return list(all_proxies)

def fetch_proxies(url, prefix):
    global total_proxies_fetched 

    try:
        response = requests.get(url)
        response.raise_for_status()

        proxies = response.text.splitlines()
        if not "api.proxyscrape.com" in url:
            formatted_proxies = [f"{prefix}://{proxy}" for proxy in proxies]
        else:
            formatted_proxies = [f"{proxy}" for proxy in proxies]

        with lock:
            total_proxies_fetched += len(formatted_proxies)

        return formatted_proxies

    except requests.RequestException as e:
        print(f"Error fetching the proxy list from {url}: {e}")
        return []

def save_proxies(proxies):
    try:
        with open("auto_proxies.txt", "r") as f:
            existing_proxies = set(f.read().splitlines())
        new_proxies = set(proxies)
        unique_proxies = new_proxies - existing_proxies

        if unique_proxies:
            with open("auto_proxies.txt", "a") as f:
                f.write("\n".join(unique_proxies) + "\n")
        else:
            print("")

    except FileNotFoundError:
        with open("auto_proxies.txt", "w") as f:
            f.write("\n".join(proxies) + "\n")
    except Exception as e:
        print(f"Error saving proxies: {e}")

def http_from_open():
    proxies = fetch_proxies("https://api.openproxylist.xyz/http.txt", "http")
    save_proxies(proxies)

def sock4_from_open():
    proxies = fetch_proxies("https://api.openproxylist.xyz/socks4.txt", "socks4")
    save_proxies(proxies)

def sock5_from_open():
    proxies = fetch_proxies("https://api.openproxylist.xyz/socks5.txt", "socks5")
    save_proxies(proxies)

def sock5_from_prlist():
    proxies = fetch_proxies("https://www.proxy-list.download/api/v1/get?type=socks5", "socks5")
    save_proxies(proxies)

def sock4_from_prlist():
    proxies = fetch_proxies("https://www.proxy-list.download/api/v1/get?type=socks4", "socks4")
    save_proxies(proxies)

def http_from_prlist():
    proxies = fetch_proxies("https://www.proxy-list.download/api/v1/get?type=http", "http")
    save_proxies(proxies)

def scrap_from_apisc():
    proxies = fetch_proxies("https://api.proxyscrape.com/v3/free-proxy-list/get?request=displayproxies&proxy_format=protocolipport", "")
    save_proxies(proxies)

def fetch_and_save_geonode_proxies():
    proxies = fetch_proxies_from_multiple_pages(1, 15)
    save_proxies(proxies)

def fetch_proxies_main():
    threads = [
            threading.Thread(target=http_from_open),
            threading.Thread(target=sock4_from_open),
            threading.Thread(target=sock5_from_open),
            threading.Thread(target=sock4_from_prlist),
            threading.Thread(target=sock5_from_prlist),
            threading.Thread(target=http_from_prlist),
            threading.Thread(target=scrap_from_apisc),
            threading.Thread(target=fetch_and_save_geonode_proxies)
        ]
        
    for thread in threads:
        thread.start()
        
    for thread in threads:
        thread.join()

    print(f"Total proxies fetched: {total_proxies_fetched}")
    print("All proxy fetching and saving tasks completed.")

async def main():
    try:
        _user_id = "2p4GgmhEwvn4B8NPpwyxHnAbzjk"
        if not _user_id:
            return
        print(f"User ID: {_user_id}")
    except FileNotFoundError:
        print("Error: user not entered yet!")
        return

    fetch_proxies_main()

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
