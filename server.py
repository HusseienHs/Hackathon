import socket
import struct
import threading
import time

from shared import create_offer_packet, create_request_packet, create_payload_packet, MAGIC_COOKIE, OFFER_TYPE, REQUEST_TYPE, PAYLOAD_TYPE, RED, GREEN, YELLOW, RESET, CYAN

class Server:
    def __init__(self, udp_port, tcp_port):
        self.udp_port = udp_port
        self.tcp_port = tcp_port
        self.udp_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.udp_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.udp_socket.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
        self.udp_socket.bind(("", udp_port))
        self.tcp_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.tcp_socket.bind(("", tcp_port))
        self.tcp_socket.listen(5)

    def broadcast_offers(self):
        offer_packet = create_offer_packet(self.udp_port, self.tcp_port)
        while True:
            self.udp_socket.sendto(offer_packet, ('<broadcast>', 13117))
            time.sleep(1)

    def handle_udp_request(self, data, client_address):
        try:
            magic_cookie, message_type, file_size = struct.unpack('!IBQ', data)
            if magic_cookie != MAGIC_COOKIE or message_type != REQUEST_TYPE:
                print(f"{RED}Invalid request from {client_address}{RESET}")
                return

            total_segments = file_size // 1024 + (1 if file_size % 1024 != 0 else 0)
            for i in range(total_segments):
                payload = b'x' * 1

                packet = create_payload_packet(total_segments, i + 1, payload)
                if len(packet) < 21:
                    print(f"{RED}Generated a packet smaller than expected.{RESET}")
                self.udp_socket.sendto(packet, client_address)
        except Exception as e:
            print(f"{RED}Error handling UDP request: {e}{RESET}")

    def udp_listener(self):
        while True:
            data, client_address = self.udp_socket.recvfrom(1024)
            threading.Thread(target=self.handle_udp_request, args=(data, client_address)).start()

    def handle_tcp_request(self, client_socket):
        try:
            file_size = int(client_socket.recv(1024).decode().strip())
            payload = b'x' * 1

            total_segments = file_size // 1024 + (1 if file_size % 1024 != 0 else 0)

            for _ in range(total_segments):
                client_socket.sendall(payload)

        except Exception as e:
            print(f"{RED}Error handling TCP request: {e}{RESET}")
        finally:
            client_socket.close()

    def tcp_listener(self):
        while True:
            client_socket, _ = self.tcp_socket.accept()
            threading.Thread(target=self.handle_tcp_request, args=(client_socket,)).start()

    def run(self):
        ip_address = socket.gethostbyname(socket.gethostname())
        print(f"{GREEN}Server started, listening on IP address {ip_address}{RESET}")

        threading.Thread(target=self.broadcast_offers, daemon=True).start()
        threading.Thread(target=self.udp_listener, daemon=True).start()
        self.tcp_listener()

if __name__ == "__main__":
    udp_port = 8000
    tcp_port = 8001
    server = Server(udp_port, tcp_port)
    server.run()
