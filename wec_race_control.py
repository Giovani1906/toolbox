import json
import time
import sys

import websocket

txt = {'new': '', 'old': ''}


def on_open(socket: websocket.WebSocketApp):
    print("")
    socket.send('{"type":"connection_init","payload":{"locale":"en"}}')


def on_message(socket: websocket.WebSocketApp, message: str):
    msg_json = json.loads(message)
    if "type" in msg_json:
        if msg_json["type"] == "connection_ack":
            sub_msg = {
                "id": "6ac611f3-a7f7-4231-8fcd-58099a239fc5",
                "type": "subscribe",
                "payload": {
                    "variables": {
                        "sessionId": "7572"
                    },
                    "extensions": {},
                    "operationName": "RaceControl",
                    "query": "subscription RaceControl($sessionId: ID!) {\n  session(sessionId: $sessionId) {\n    id\n    raceControl {\n      messages {\n        id\n        ...RaceControlMessage\n        __typename\n      }\n      __typename\n    }\n    __typename\n  }\n}\n\nfragment RaceControlMessage on RaceControlMessage {\n  id\n  text\n  backgroundColor\n  dayTime\n  __typename\n}"
                }
            }
            socket.send(json.dumps(sub_msg))
        if msg_json["type"] == "next":
            msg_list = [item['text'] for item in msg_json['payload']['data']['session']['raceControl']['messages']]
            txt['new'] = '\n'.join(msg_list[:5])

            if txt['new'] != txt['old']:
                with open('message.txt', 'w') as f:
                    f.write(txt['new'])

                sys.stdout.write(txt['new'])
                sys.stdout.write("\033[F"*4)
                sys.stdout.flush()
                txt['old'] = txt['new']


def on_error(socket: websocket.WebSocketApp, error):
    print(error)


def on_close(socket: websocket.WebSocketApp, close_status_code, close_msg):
    print("Connection closed...")
    if close_status_code:
        print(f"close status code: {close_status_code}")
    if close_msg:
        print(f"close message: {close_msg}")


if __name__ == "__main__":
    try:
        # websocket.enableTrace(True)
        ws_kwargs = {
            "url": 'wss://live-timing-api.sportall.tv/graphql',
            "subprotocols": ["graphql-transport-ws"],
            "on_open": on_open,
            "on_message": on_message,
            "on_error": on_error,
            "on_close": on_close,
        }
        ws = websocket.WebSocketApp(**ws_kwargs)
        ws.run_forever()
    except KeyboardInterrupt:
        print("Exiting...")
        time.sleep(1)
        exit(0)
