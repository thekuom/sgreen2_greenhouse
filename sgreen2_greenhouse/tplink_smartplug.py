import json
import socket


class TpLinkSmartplug:
    """
    A class for controlling a TP-Link smartplug
    """

    def __init__(self, ip: str, port: int):
        """
        The constructor
        :param ip: the ip address of the TP-Link smartplug
        :param port: the port of the TP-Link smartplug
        """
        self.ip = ip
        self.port = port
        self.commands = {'info': '{"system":{"get_sysinfo":{}}}',
                         'on': '{"system":{"set_relay_state":{"state":1}}}',
                         'off': '{"system":{"set_relay_state":{"state":0}}}',
                         'cloudinfo': '{"cnCloud":{"get_info":{}}}',
                         'wlanscan': '{"netif":{"get_scaninfo":{"refresh":0}}}',
                         'time': '{"time":{"get_time":{}}}',
                         'schedule': '{"schedule":{"get_rules":{}}}',
                         'countdown': '{"count_down":{"get_rules":{}}}',
                         'antitheft': '{"anti_theft":{"get_rules":{}}}',
                         'reboot': '{"system":{"reboot":{"delay":1}}}',
                         'reset': '{"system":{"reset":{"delay":1}}}'
                         }

    @staticmethod
    def __encrypt(string: str) -> str:
        """
        Encrypts data based on what the TP-Link smartplug is expecting
        :param string: the string to encrypt
        :return: the encrypted result
        """
        key = 171
        result = b"\0\0\0" + chr(len(string)).encode('latin-1')
        for i in string.encode('latin-1'):
            a = key ^ i
            key = a
            result += chr(a).encode('latin-1')
        return result

    @staticmethod
    def __decrypt(string: str) -> str:
        """
        Decrypts data based on what the TP-Link smartplug is using
        :param string: the string to decrypt
        :return: the decrypted data
        """
        key = 171
        result = ""
        i: int
        for i in string:
            a = key ^ i
            key = i
            result += chr(a)
        return result

    def perform_command(self, cmd: str) -> dict:
        """
        Performs any TP-Link smartplug supported command. See the commands
        dictionary
        :param cmd: a json formatted command
        :return: a dictionary response
        """
        sock_tcp = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock_tcp.connect((self.ip, self.port))
        sock_tcp.send(self.__encrypt(cmd))

        data = sock_tcp.recv(2048)

        sock_tcp.close()

        data = self.__decrypt(data[4:])

        if not data:
            raise ConnectionError("Error: Could not communicate to the smart plug")

        return json.loads(data)

    def set_state(self, is_on: bool) -> None:
        """
        Turns the TP-Link smartplug on or off depending on the state
        :param is_on: whether the smartplug should be on or off
        :return: None
        """
        json_data = self.perform_command(self.commands["on"] if is_on else self.commands["off"])

        if json_data["system"]["set_relay_state"]["err_code"] != 0:
            raise Exception("Error: Error from the smartplug: " + json.dumps(json_data))
