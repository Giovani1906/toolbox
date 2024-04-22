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


def ping(socket: websocket.WebSocketApp):
    while True:
        time.sleep(socket.ping_interval)
        socket.send("2")


def on_message(socket: websocket.WebSocketApp, message: str):
    if message == "3probe":
        socket.send("5")
    else:
        if chat_message := re.match(
            r'42\["chatMsg",{"username":"(.*)","msg":"(.*)","meta":{.*},"time":(\d{13})}]',
            message,
        ):
            username, message, timestamp = chat_message.groups()
            date = datetime.datetime.fromtimestamp(int(timestamp) / 1000.0)
            output = "{0.hour:02d}:{0.minute:02d}:{0.second:02d}] {1}: {2}"
            if "span" in message:
                message = message.split("span")[0][:-2]
                print(output.format(date, username, html.unescape(message)))
            else:
                print(output.format(date, username, html.unescape(message)))


def on_error(socket: websocket.WebSocketApp, error):
    print(error)


def on_close(socket: websocket.WebSocketApp, close_status_code, close_msg):
    print("on_close args:")
    if close_status_code or close_msg:
        print(f"close status code: {close_status_code}")
        print(f"close message: {close_msg}")


def on_open(socket: websocket.WebSocketApp):
    print("\n")
    socket.send("2probe")
    threading.Thread(target=ping, args=(socket,)).start()


if __name__ == "__main__":
    mode = "4cc"

    cytube_url = {
        "4cc": "https://cytu.be/socketconfig/the4chancup.json",
        "vgl": "https://cytube.implying.fun/socketconfig/vgleague.json",
    }

    sesh = requests.Session()
    resp = sesh.request("GET", cytube_url[mode])
    server = json.loads(resp.text)["servers"][0]["url"]

    r_url = f"{server}/socket.io/?EIO=3&transport=polling&t={yeast()}"
    _sid = sesh.request("GET", r_url)
    sid = re.match(r'.*{"sid":"(.*)",.*', _sid.text).groups()[0]

    r_url += f"&sid={sid}"
    sesh.request("GET", r_url)

    # websocket.enableTrace(True)
    ws_kwargs = {
        "url": f'wss://{server.split("//")[1]}/socket.io/?EIO=3&transport=websocket&sid={sid}',
        "on_message": on_message,
        "on_error": on_error,
        "on_close": on_close,
    }
    ws = websocket.WebSocketApp(**ws_kwargs)
    ws.on_open = on_open

    thread_kwargs = {
        "target": ws.run_forever,
        "kwargs": {"ping_interval": 20, "ping_timeout": 5},
    }
    threading.Thread(**thread_kwargs).start()

    join_channel_data = {
        "4cc": '40:42["joinChannel",{"name":"the4chancup"}]',
        "vgl": '37:42["joinChannel",{"name":"vgleague"}]',
    }
    sesh.request("POST", r_url, data=join_channel_data[mode])
    sesh.request("GET", r_url)
