from aioconsole import ainput, aprint
from json import dumps, loads
from os.path import abspath
from sys import executable
from time import sleep
from sys import argv
import logging
import asyncio
import socket

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
connections = []


def local_time():
    minutes = 0
    while True:
        sleep(60)
        minutes += 1
        logging.info(f'Session time: {minutes} {"minutes" if minutes > 1 else "minute"}')


async def time_process():
    proc = await asyncio.create_subprocess_exec(executable, abspath(__file__), 'time', stdout=asyncio.subprocess.PIPE)
    while True:
        data = await proc.stdout.readline()
        line = data.decode('utf8').rstrip()
        await aprint(line)


async def send_to_client(client, data):
    loop = asyncio.get_event_loop()

    try:
        await asyncio.gather(loop.sock_sendall(client, data))
    except ConnectionResetError:
        if client in connections:
            connections.remove(client)


async def send_message(data, client=None):
    data = bytes(dumps(data), encoding="utf-8")
    if client:
        await asyncio.gather(send_to_client(client, data))
    else:
        await asyncio.gather(*(send_to_client(connection, data) for connection in connections))


async def process_request(request, connection):
    request = loads(request)
    response = {}

    if request['type'] == 'join':
        if 'forwarded' not in request:
            request['forwarded'] = True
            await send_message(request)

            response = {'type': 'response', 'message': 'Successful join'}
            connections.append(connection)
        else:
            newClient = await connect(request['host'], request['port'])
            await send_message({'type': 'connect'}, newClient)

        logging.info(f'Host {request["host"]}:{str(request["port"])} joined')
    elif request['type'] == 'connect':
        connections.append(connection)
    elif request['type'] == 'response':
        logging.info(f'Response received: {request["message"]}')
    elif request['type'] == 'message':
        logging.info(f'Message received: {request["message"]}')
    else:
        logging.warning('Unknown request type')

    return response


async def handle_data(client):
    loop = asyncio.get_event_loop()

    while True:
        try:
            data = (await loop.sock_recv(client, 255)).decode('utf8')
            response = await process_request(data, client)
            if response:
                await send_message(response, client)
        except ConnectionResetError:
            if client in connections:
                connections.remove(client)
            break


async def run_server():
    server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server.bind((argv[1], int(argv[2])))
    server.listen(10)
    server.setblocking(False)

    loop = asyncio.get_event_loop()

    logging.info(f'Listening on {argv[1]}:{argv[2]}')
    while True:
        client, _ = await loop.sock_accept(server)
        loop.create_task(handle_data(client))


async def connect(host, port):
    client = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    client.setblocking(False)

    loop = asyncio.get_event_loop()

    await loop.sock_connect(client, (host, port))
    loop.create_task(handle_data(client))
    connections.append(client)
    return client


async def join():
    client = await connect(argv[4], int(argv[5]))
    await send_message({'type': 'join', 'host': argv[1], 'port': int(argv[2])}, client)


async def message_input():
    while True:
        message = await ainput("Enter message: ")
        await send_message({'type': 'message', 'message': message})


if __name__ == "__main__":
    loop_ = asyncio.get_event_loop()

    if len(argv) == 2 and argv[1] == 'time':
        local_time()
        exit(0)
    elif len(argv) == 3:
        loop_.run_until_complete(asyncio.gather(
            time_process(),
            run_server(),
            message_input()
        ))
    elif len(argv) == 6:
        loop_.run_until_complete(asyncio.gather(
            time_process(),
            run_server(),
            join(),
            message_input()
        ))
    else:
        logging.error('Invalid parameters provided, see README')
        exit(1)
