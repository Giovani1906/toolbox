import argparse
import datetime
import html
import json
import math
import re
import threading
import time

import requests
import websocket

alphabet = "0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz-_"
length = 64
seed = 0
prev = None


def encode(num):
    encoded = ""
    while True:
        encoded = alphabet[int(num % length)] + encoded
        num = math.floor(num / length)
        # simulate do-while
        if not (num > 0):
            break
    return encoded


def yeast():
    global prev, seed
    ts = int(time.time() * 1000)
    now = encode(ts)
    if now != prev:
        seed = 0
        prev = now
        return now
    else:
        r = now + "." + encode(seed)
        seed += 1
        return r


def get_url(server_addr: str, eio_mode: str, _sid: str = None):
    eio = 4 if eio_mode == "4cc" else 3
    if not _sid:
        return f"{server_addr}/socket.io/?EIO={eio}&transport=polling&t={yeast()}"
    return (
        f"{server_addr}/socket.io/?EIO={eio}&transport=polling&t={yeast()}&sid={_sid}"
    )


def ping(socket: websocket.WebSocketApp):
    while True:
        time.sleep(socket.ping_interval)
        socket.send("2")


def on_message(socket: websocket.WebSocketApp, message: str):
    if message == "3probe":
        socket.send("5")
    elif message == "2" and mode == "4cc":
        socket.send("3")
    else:
        if chat_message := re.match(
            r'42\["chatMsg",{"username":"(.*)","msg":"(.*)","meta":{.*},"time":(\d{13})}]',
            message,
        ):
            username, message, timestamp = chat_message.groups()
            date = datetime.datetime.fromtimestamp(int(timestamp) / 1000.0)
            output = "[{0.hour:02d}:{0.minute:02d}:{0.second:02d}] {1}: {2}"
            if "span" in message:
                message = message.split("span")[0][:-2]
                print(output.format(date, username, html.unescape(message)))
            else:
                print(output.format(date, username, html.unescape(message)))


def on_error(socket: websocket.WebSocketApp, error):
    print(error)


def on_close(socket: websocket.WebSocketApp, close_status_code, close_msg):
    print("Connection closed...")
    if close_status_code:
        print(f"close status code: {close_status_code}")
    if close_msg:
        print(f"close message: {close_msg}")


def on_open(socket: websocket.WebSocketApp):
    print("")
    socket.send("2probe")
    if mode != "4cc":
        threading.Thread(target=ping, args=(socket,)).start()


if __name__ == "__main__":
    try:
        parser = argparse.ArgumentParser(prog="Cytube Scrapper")
        parser.add_argument("mode", nargs="?", default="4cc", choices=["4cc", "vgl"])
        mode = parser.parse_args().mode

        print(f"Cytube Scrapper\n\nRunning in {mode} mode.")

        cytube_url = {
            "4cc": "https://cytu.be/socketconfig/the4chancup.json",
            "vgl": "https://cytube.implying.fun/socketconfig/vgleague.json",
        }

        sesh = requests.Session()
        resp = sesh.request("GET", cytube_url[mode])
        serv = json.loads(resp.text)["servers"][0]["url"]

        serv_info_raw = sesh.request("GET", get_url(serv, mode))
        regex = re.compile(r"[\d\W]*({.*})")
        serv_info = json.loads(regex.match(serv_info_raw.text).groups()[0])
        sid = serv_info["sid"]

        if mode == "4cc":
            sesh.request("POST", get_url(serv, mode, sid), data="40")
        sesh.request("GET", get_url(serv, mode, sid))

        # websocket.enableTrace(True)
        ws_url = {
            "4cc": f"wss://{serv.split("//")[1]}/socket.io/?EIO=4&transport=websocket&sid={sid}",
            "vgl": f"wss://{serv.split("//")[1]}/socket.io/?EIO=3&transport=websocket&sid={sid}",
        }
        ws_kwargs = {
            "url": ws_url[mode],
            "on_message": on_message,
            "on_error": on_error,
            "on_close": on_close,
        }
        ws = websocket.WebSocketApp(**ws_kwargs)
        ws.on_open = on_open

        thread_kwargs = {
            "target": ws.run_forever,
            "kwargs": {
                "ping_interval": serv_info["pingInterval"],
                "ping_timeout": 10,
            },
        }
        threading.Thread(**thread_kwargs).start()

        join_channel_data = {
            "4cc": '42["joinChannel",{"name":"the4chancup"}]',
            "vgl": '37:42["joinChannel",{"name":"vgleague"}]',
        }
        sesh.request("POST", get_url(serv, mode, sid), data=join_channel_data[mode])
        sesh.request("GET", get_url(serv, mode, sid))
    except KeyboardInterrupt:
        print("Exiting...")
        time.sleep(1)
        exit(0)
