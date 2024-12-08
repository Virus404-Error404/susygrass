import ssl
import json
import time
import uuid
import random
import asyncio
import threading
import requests
from loguru import logger
from fake_useragent import UserAgent
from websockets_proxy import Proxy, proxy_connect
from queue import Queue

total_proxies_fetched = 0
lock = threading.Lock()
proxy_queue = Queue()

async def connect_to_wss(socks5_proxy, user_id):
    user_agent = UserAgent(os=['windows', 'macos', 'linux'], browsers='chrome')
    random_user_agent = user_agent.random
    device_id = str(uuid.uuid3(uuid.NAMESPACE_DNS, socks5_proxy))
    logger.info(f"Connecting using proxy: {socks5_proxy}")
    while True:
        try:
            await asyncio.sleep(random.randint(1, 10) / 10)
            custom_headers = {"User-Agent": random_user_agent}
            ssl_context = ssl.create_default_context()
            ssl_context.check_hostname = False
            ssl_context.verify_mode = ssl.CERT_NONE
            urilist = ["wss://proxy2.wynd.network:4444/", "wss://proxy2.wynd.network:4650/"]
            uri = random.choice(urilist)
            server_hostname = "proxy2.wynd.network"
            proxy = Proxy.from_url(socks5_proxy)

            async with proxy_connect(uri, proxy=proxy, ssl=ssl_context, server_hostname=server_hostname, extra_headers=custom_headers) as websocket:
                async def send_ping():
                    while True:
                        send_message = json.dumps({
                            "id": str(uuid.uuid4()), "version": "1.0.0", "action": "PING", "data": {}
                        })
                        logger.debug(f"Sending PING: {send_message}")
                        await websocket.send(send_message)
                        await asyncio.sleep(5)

                asyncio.create_task(send_ping())

                while True:
                    response = await websocket.recv()
                    message = json.loads(response)
                    logger.info(f"Received message: {message}")

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
                        logger.debug(f"Sending AUTH: {auth_response}")
                        await websocket.send(json.dumps(auth_response))

                    elif message.get("action") == "PONG":
                        pong_response = {"id": message["id"], "origin_action": "PONG"}
                        logger.debug(f"Sending PONG: {pong_response}")
                        await websocket.send(json.dumps(pong_response))

        except Exception as e:
            logger.error(f"Connection failed with proxy {socks5_proxy}: {e}")
            with open('auto_proxies.txt', 'r', encoding='utf-8') as file:
                lines = file.readlines()
            updated_lines = [line for line in lines if line.strip() != socks5_proxy]
            with open('auto_proxies.txt', 'w', encoding='utf-8') as file:
                file.writelines(updated_lines)
            logger.info(f"Proxy '{socks5_proxy}' has been removed from the file.")
            break

def fetch_from_url(url, prefix):
    global proxies
    proxies = set()
    try:
        response = requests.get(url)
        response.raise_for_status()
        proxy_list = response.text.splitlines()
        logger.info(f"Fetched {len(proxy_list)} proxies from {url}")

        for proxy in proxy_list:
            if "://" not in proxy and ":" in proxy:
                proxies.add(f"{prefix}://{proxy}")
            elif "://" in proxy:
                proxies.add(proxy)
            else:
                logger.warning(f"Skipping invalid proxy format: {proxy}")

    except requests.RequestException as e:
        logger.error(f"Error fetching proxies from {url}: {e}")

    return proxies

def save_proxies(proxies):
    valid_proxies = []
    for proxy in proxies:
        if isinstance(proxy, str) and "://" in proxy and ":" in proxy:
            valid_proxies.append(proxy)
        else:
            logger.warning(f"Invalid proxy format: {proxy}")

    try:
        with open("auto_proxies.txt", "w", encoding='utf-8') as f:
            for proxy in valid_proxies:
                f.write(f"{proxy}\n")
        logger.info(f"Saved {len(valid_proxies)} new proxies to 'auto_proxies.txt'.")
    except Exception as e:
        logger.error(f"Error saving proxies: {e}")

async def fetch_proxies_from_multiple_sources():
    global total_proxies_fetched

    proxy_urls = [
        ("https://api.openproxylist.xyz/http.txt", "http"),
        ("https://api.openproxylist.xyz/socks4.txt", "socks4"),
        ("https://api.openproxylist.xyz/socks5.txt", "socks5"),
        ("https://www.proxy-list.download/api/v1/get?type=socks5", "socks5"),
        ("https://www.proxy-list.download/api/v1/get?type=socks4", "socks4"),
        ("https://www.proxy-list.download/api/v1/get?type=http", "http"),
        ("https://api.proxyscrape.com/v3/free-proxy-list/get?request=displayproxies&proxy_format=protocolipport", ""),
        ("https://proxylist.geonode.com/api/proxy-list?limit=500&page=14&sort_by=lastChecked&sort_type=desc", "")
    ]

    threads = []
    for url, prefix in proxy_urls:
        thread = threading.Thread(target=fetch_from_url, args=(url, prefix))
        threads.append(thread)
        thread.start()

    for thread in threads:
        thread.join()

    logger.info(f"Total proxies fetched: {len(proxies)}")
    return list(proxies)

async def check_proxies():
    while True:
        proxy = proxy_queue.get()
        if proxy is None:
            break

        logger.info(f"Checking proxy {proxy}")
        await connect_to_wss(proxy, user_id="2p4GgmhEwvn4B8NPpwyxHnAbzjk")
        await asyncio.sleep(0.01)

        proxy_queue.task_done()

async def main():
    proxies = await fetch_proxies_from_multiple_sources()
    if not proxies:
        logger.error("No proxies fetched. Exiting script.")
        return

    logger.info(f"Total unique proxies fetched: {len(proxies)}")
    
    save_proxies(proxies)

    try:
        with open('auto_proxies.txt', 'r', encoding='utf-8') as file:
            auto_proxy_list = file.read().splitlines()
            if not auto_proxy_list:
                logger.error("No proxies found in 'auto_proxies.txt'. Exiting script.")
                return
            logger.info(f"Proxies read from file: {auto_proxy_list}")
    except FileNotFoundError:
        logger.error("Error: 'auto_proxies.txt' file not found. Exiting script.")
        return

    for proxy in auto_proxy_list:
        proxy_queue.put(proxy)

    logger.info(f"Starting proxy check for {len(auto_proxy_list)} proxies.")
    tasks = [asyncio.create_task(check_proxies()) for _ in range(1000)]
    await asyncio.gather(*tasks)

if __name__ == "__main__":
    asyncio.run(main())
