import re
import socket
import ssl
import sys
import threading

from codes import Code


class IRCClient:
    def __init__(self, server, nickname, port=None, tls=False, username=None, realname=None, encoding='utf-8', errors='ignore', capabilities=None):
        self.server = server
        self.nickname = nickname
        if not self.nickname:
            raise ValueError("Nick must not be empty")
        if port is None:
            if tls:
                self.port = 6697
            else:
                self.port = 6667
        else:
            self.port = port
        self.tls = tls
        if not username:
            self.username = self.nickname
        else:
            self.username = username
        if not realname:
            self.realname = self.username
        else:
            self.realname = realname
        self.encoding = encoding
        self.errors = errors
        if capabilities is None:
            capabilities = []
        self.capabilities = capabilities
        self.enabled_capabilities = []
        self.socket_mutex = threading.Lock()

    def start(self):
        self.socket = socket.create_connection((self.server, self.port))
        if self.tls:
            self.raw_socket = self.socket
            context = ssl.create_default_context()
            self.socket = context.wrap_socket(self.raw_socket, server_hostname=self.server)
        if self.capabilities:
            self.cap_ls(True)
        self.nick(self.nickname)
        self.user(self.username, self.realname)
        threads = []
        while True:
            data = b''
            while not data or data[-1] != ord('\n'):
                data += self.socket.recv(4096)
            data = data.decode(self.encoding, self.errors).split('\r\n')
            for command in data:
                if command:
                    thread = threading.Thread(target=self.process_command, args=(command,))
                    thread.start()
                    threads.append(thread)

    @staticmethod
    def parse_command_params(params):
        result = []
        last_param = 0
        for i, char in enumerate(params):
            if char == ' ':
                if params[i+1] == ':':
                    result.append(params[last_param:i])
                    result.append(params[i+2:])
                    last_param = len(params)
                    break
                else:
                    result.append(params[last_param:i])
                    last_param = i+1
            elif i == 0 and char == ':':
                result.append(params[i+1:])
                last_param = len(params)
                break
        if last_param != len(params):
            result.append(params[last_param:])
        return result

    @staticmethod
    def parse_tags(tags):
        if tags[0] != '@':
            raise ValueError("Invalid tags")
        result = {}
        tags = tags[1:].split(';')
        for tag in tags:
            if '=' in tag:
                tag = tag.split('=', 1)
                result[tag[0]] = tag[1]
            else:
                result[tag] = None
        return result

    def process_command(self, command):
        match = re.match(r'^(?P<tags>@(?:(?:\+?(?:[0-9A-Za-z.-]+/)?[0-9A-Za-z-]+)(?:=[^\x00\r\n; ]+)?)?(?:;(?:\+?(?:[0-9A-Za-z.-]+/)?[0-9A-Za-z-]+)(?:=[^\x00\r\n; ]+)?)*)? *(?::(?P<target>[^ ]*))? *(?P<command>[a-zA-Z]+|[0-9]{3}) *(?:(?P<params>.*?))?$', command)
        if match is None:
            print('Unknown command:', command, file=sys.stderr)
            return
        tags = match.group('tags')
        if tags is not None:
            tags = self.parse_tags(tags)
        else:
            tags = {}
        target = match.group('target')
        command = match.group('command')
        params = self.parse_command_params(match.group('params'))
        print('<=', tags, target, command, params)
        if command.isnumeric():
            command = int(command)
        try:
            command = Code(command)
        except ValueError:
            self.on_command(command, *params, target=target, tags=tags)
        if command == Code.CAP:
            if params[1] == 'ACK':
                self.on_cap_ack(params[2], target=target, tags=tags)
            elif params[1] == 'LS':
                self.on_cap_ls(params[2], target=target, tags=tags)
        elif command == Code.INVITE:
            self.on_invite(*params, target=target, tags=tags)
        elif command == Code.JOIN:
            self.on_join(*params, target=target, tags=tags)
        elif command == Code.PING:
            self.on_ping(*params, target=target, tags=tags)
        elif command == Code.PRIVMSG:
            self.on_privmsg(*params, target=target, tags=tags)
        elif command == Code.RPL_ENDOFWHOIS:
            self.on_endofwhois(*params, target=target, tags=tags)
        elif command == Code.RPL_WELCOME:
            self.on_welcome(*params, target=target, tags=tags)
        elif command == Code.RPL_WHOISACCOUNT:
            self.on_whoisaccount(*params, target=target, tags=tags)
        elif command == Code.RPL_WHOISREGNICK:
            self.on_whoisregnick(*params, target=target, tags=tags)

    def cap_end(self):
        self.socket_mutex.acquire()
        self.socket.sendall(f'{Code.CAP.value} END\r\n'.encode(self.encoding))
        self.socket_mutex.release()

    def cap_ls(self, _302=False):
        self.socket_mutex.acquire()
        if self.capabilities:
            if _302:
                self.socket.sendall(f'{Code.CAP.value} LS 302\r\n'.encode(self.encoding))
            else:
                self.socket.sendall(f'{Code.CAP.value} LS\r\n'.encode(self.encoding))
        self.socket_mutex.release()

    def cap_req(self, capabilities=None):
        self.socket_mutex.acquire()
        if capabilities is None:
            capabilities = self.capabilities
        capabilities = ' '.join(capabilities)
        self.socket.sendall(f'{Code.CAP.value} REQ :{capabilities}\r\n'.encode(self.encoding))
        self.socket_mutex.release()

    def invite(self, nickname, channel):
        self.socket_mutex.acquire()
        self.socket.sendall(f'{Code.INVITE.value} {nickname} {channel}\r\n'.encode(self.encoding))
        self.socket_mutex.release()

    def join(self, channel):
        self.socket_mutex.acquire()
        self.socket.sendall(f'{Code.JOIN.value} {channel}\r\n'.encode(self.encoding))
        self.socket_mutex.release()

    def nick(self, nickname):
        self.socket_mutex.acquire()
        self.socket.sendall(f'{Code.NICK.value} {nickname}\r\n'.encode(self.encoding))
        self.socket_mutex.release()

    def pong(self, data):
        self.socket_mutex.acquire()
        self.socket.sendall(f'{Code.PONG.value} :{data}\r\n'.encode(self.encoding))
        self.socket_mutex.release()

    def privmsg(self, channel, message):
        self.socket_mutex.acquire()
        messages = message.split('\n')
        for message in messages:
            self.socket.sendall(f'{Code.PRIVMSG.value} {channel} :{message}\r\n'.encode(self.encoding))
        self.socket_mutex.release()

    def user(self, username, realname, mode=0):
        self.socket_mutex.acquire()
        self.socket.sendall(f'{Code.USER.value} {username} {mode} * :{realname}\r\n'.encode(self.encoding))
        self.socket_mutex.release()

    def whois(self, *masks, target=None):
        self.socket_mutex.acquire()
        masks = ' '.join(masks)
        if target is None:
            self.socket.sendall(f'{Code.WHOIS.value} {masks}\r\n'.encode(self.encoding))
        else:
            self.socket.sendall(f'{Code.WHOIS.value} {target} {masks}\r\n'.encode(self.encoding))
        self.socket_mutex.release()

    def on_cap_ack(self, capabilities, target, tags):
        self.enabled_capabilities = capabilities.split()
        self.cap_end()

    def on_cap_ls(self, capabilities, target, tags):
        capabilities = capabilities.split()
        self.enabled_capabilities = [capability for capability in self.capabilities if capability in capabilities]
        self.cap_req(self.enabled_capabilities)

    def on_endofwhois(self, nickname, whoisnickname, info, target, tags):
        pass

    def on_invite(self, nickname, channel, target, tags):
        pass

    def on_join(self, channel, accountname='*', realname=None, target=None, tags=None):
        pass

    def on_ping(self, data, target, tags):
        self.pong(data)

    def on_privmsg(self, channel, message, target, tags):
        pass

    def on_welcome(self, nickname, reply, target, tags):
        pass

    def on_whoisaccount(self, nickname, whoisnickname, account, info, target, tags):
        pass

    def on_whoisregnick(self, nickname, whoisnickname, reply, target, tags):
        pass

    def on_command(code, *params, target=None, tags=None):
        pass
