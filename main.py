import socket
import struct
import threading
import time

MAGIC_COOKIE = 0xabcddcba
OFFER_TYPE = 0x2
REQUEST_TYPE = 0x3
PAYLOAD_TYPE = 0x4

# ANSI Color Codes
RED = "\033[91m"
GREEN = "\033[92m"
YELLOW = "\033[93m"
BLUE = "\033[94m"
MAGENTA = "\033[95m"
CYAN = "\033[96m"
RESET = "\033[0m"


def create_offer_packet(udp_port, tcp_port):
    return struct.pack('!IBHH', MAGIC_COOKIE, OFFER_TYPE, udp_port, tcp_port)


def create_request_packet(file_size):
    return struct.pack('!IBQ', MAGIC_COOKIE, REQUEST_TYPE, file_size)


def create_payload_packet(total_segments, current_segment, payload):
    header = struct.pack('!IBQQ', MAGIC_COOKIE, PAYLOAD_TYPE, total_segments, current_segment)
    return header + payload


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
                payload = b'x' * 1024 if i < total_segments - 1 else b'x' * (file_size % 1024)
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
            payload = b'x' * 1024
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
        # Get the server's IP address
        ip_address = socket.gethostbyname(socket.gethostname())
        print(f"{GREEN}Server started, listening on IP address {ip_address}{RESET}")

        threading.Thread(target=self.broadcast_offers, daemon=True).start()
        threading.Thread(target=self.udp_listener, daemon=True).start()
        self.tcp_listener()


class Client:
    def __init__(self):
        self.udp_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.udp_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.udp_socket.bind(('', 13117))
        self.total_udp_segments = 0
        self.transfer_counter = 1  # Track the number of transfers

    def listen_for_offers(self):
        print(f"{CYAN}Client started, listening for offer requests...{RESET}")
        self.udp_socket.settimeout(40)
        try:
            while True:
                try:
                    data, server_address = self.udp_socket.recvfrom(1024)
                    magic_cookie, message_type, udp_port, tcp_port = struct.unpack('!IBHH', data)

                    if magic_cookie == MAGIC_COOKIE and message_type == OFFER_TYPE:
                        print(f"{GREEN}Received offer from {server_address}: UDP {udp_port}, TCP {tcp_port}{RESET}")
                        return server_address[0], udp_port, tcp_port

                except socket.timeout as e:
                    print(f"{YELLOW}Socket timeout occurred: {e}{RESET}")
                    continue
                except Exception as e:
                    print(f"{RED}Error receiving UDP offer: {e}{RESET}")
                    continue
        except Exception as e:
            print(f"{RED}Error in listen_for_offers: {e}{RESET}")
        # Remove closing here and let the socket stay open throughout the client run

    def send_udp_request(self, server_address, udp_port, file_size):
        try:
            request_packet = create_request_packet(file_size)
            udp_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            udp_socket.settimeout(1)

            start_time = time.time()
            udp_socket.sendto(request_packet, (server_address, udp_port))

            receiving_udp_segments = 0
            total_segments = file_size // 1024 + (1 if file_size % 1024 != 0 else 0)
            last_segment = time.time()

            while True:
                try:
                    data, _ = udp_socket.recvfrom(2048)

                    if len(data) < 21:  # 21 bytes is the minimum size of a valid payload packet
                        print(f"{RED}Received an invalid UDP packet (too small). Skipping...{RESET}")
                        continue
                    receiving_udp_segments += 1
                    last_segment = time.time()

                    magic_cookie, message_type, total_segments, current_segment = struct.unpack('!IBQQ', data[:21])

                    if magic_cookie != MAGIC_COOKIE or message_type != PAYLOAD_TYPE:
                        print(f"{RED}Invalid payload received. Skipping...{RESET}")
                        continue

                    if not (1 <= current_segment <= total_segments):
                        print(f"{RED}Out-of-range segment: {current_segment}/{total_segments}{RESET}")
                        continue

                    if current_segment == total_segments:
                        break
                except socket.timeout as e:
                    if time.time() - last_segment > 1:
                        print(f"{RED}UDP transfer timed out. Exiting...{RESET}")
                        break

            udp_time = (time.time() - start_time)  # seconds
            udp_speed = (file_size * 8) / udp_time  # bits/second
            udp_loss = max(0, 100 * (1 - (receiving_udp_segments / total_segments)))

            print(f"{GREEN}UDP transfer #{self.transfer_counter} finished, total time: {udp_time:.2f} seconds, "
                  f"total speed: {udp_speed:.2f} bits/second, percentage of packets received successfully: "
                  f"{100 - udp_loss:.2f}%{RESET}")
            self.transfer_counter += 1

        finally:
            udp_socket.close()

    def send_tcp_request(self, server_address, tcp_port, file_size):
        tcp_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        tcp_socket.connect((server_address, tcp_port))
        tcp_socket.sendall(f"{file_size}\n".encode())

        start_time = time.time()
        received_bytes = 0
        while received_bytes < file_size:
            data = tcp_socket.recv(1024)
            if not data:
                break
            received_bytes += len(data)
            print(f"{YELLOW}Received {received_bytes} bytes{RESET}")

        end_time = time.time()
        tcp_time = (end_time - start_time)  # seconds
        tcp_speed = (file_size * 8) / tcp_time  # bits/second

        print(f"{GREEN}TCP transfer #{self.transfer_counter} finished, total time: {tcp_time:.2f} seconds, "
              f"total speed: {tcp_speed:.2f} bits/second{RESET}")
        self.transfer_counter += 1
        tcp_socket.close()

    def run(self):
        while True:
            print(f"{CYAN}Looking for a server...{RESET}")
            try:
                server_address, udp_port, tcp_port = self.listen_for_offers()

                # Get file size and number of connections from the user
                file_size = int(input(f"{YELLOW}Enter file size for transfer (in bytes): {RESET}"))
                num_udp_connections = int(input(f"{YELLOW}Enter number of UDP connections: {RESET}"))
                num_tcp_connections = int(input(f"{YELLOW}Enter number of TCP connections: {RESET}"))

                self.total_udp_segments = file_size // 1024 + (1 if file_size % 1024 != 0 else 0)

                # Start multiple UDP connections
                print(f"{CYAN}Testing {num_udp_connections} UDP transfer(s)...{RESET}")
                udp_threads = []
                for _ in range(num_udp_connections):
                    udp_thread = threading.Thread(target=self.send_udp_request, args=(server_address, udp_port, file_size))
                    udp_thread.start()
                    udp_threads.append(udp_thread)

                # Start multiple TCP connections
                print(f"{CYAN}Testing {num_tcp_connections} TCP transfer(s)...{RESET}")
                tcp_threads = []
                for _ in range(num_tcp_connections):
                    tcp_thread = threading.Thread(target=self.send_tcp_request, args=(server_address, tcp_port, file_size))
                    tcp_thread.start()
                    tcp_threads.append(tcp_thread)

                # Wait for all UDP threads to complete
                for thread in udp_threads:
                    thread.join()

                # Wait for all TCP threads to complete
                for thread in tcp_threads:
                    thread.join()

                print(f"{GREEN}All transfers complete, listening to offer requests...{RESET}")

            except Exception as e:
                print(f"{RED}Error in client: {e}{RESET}")



if __name__ == "__main__":
    role = input(f"{YELLOW}Are you running the server or client? (server/client): {RESET}").strip().lower()

    if role == "server":
        udp_port = 6000
        tcp_port = 6001
        server = Server(udp_port, tcp_port)
        server.run()

    elif role == "client":
        client = Client()
        client.run()

    else:
        print(f"{RED}Invalid role. Please enter 'server' or 'client'.{RESET}")
