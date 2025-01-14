import socket
import struct
import threading
import time

MAGIC_COOKIE = 0xabcddcba
OFFER_TYPE = 0x2
REQUEST_TYPE = 0x3
PAYLOAD_TYPE = 0x4

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
                print(f"Invalid request from {client_address}")
                return

            total_segments = file_size // 1024 + (1 if file_size % 1024 != 0 else 0)
            for i in range(total_segments):
                payload = b'x' * 1024 if i < total_segments - 1 else b'x' * (file_size % 1024)
                packet = create_payload_packet(total_segments, i + 1, payload)
                if len(packet) < 21:
                    print("Generated a packet smaller than expected.")
                self.udp_socket.sendto(packet, client_address)
        except Exception as e:
            print(f"Error handling UDP request: {e}")

    def udp_listener(self):
        while True:
            data, client_address = self.udp_socket.recvfrom(1024)
            threading.Thread(target=self.handle_udp_request, args=(data, client_address)).start()

    def handle_tcp_request(self, client_socket):
        file_size = int(client_socket.recv(1024).decode().strip())
        payload = b'x' * 1024
        total_segments = file_size // 1024 + (1 if file_size % 1024 != 0 else 0)

        for _ in range(total_segments):
            client_socket.sendall(payload)

        client_socket.close()

    def tcp_listener(self):
        while True:
            client_socket, _ = self.tcp_socket.accept()
            threading.Thread(target=self.handle_tcp_request, args=(client_socket,)).start()

    def run(self):
        threading.Thread(target=self.broadcast_offers, daemon=True).start()
        threading.Thread(target=self.udp_listener, daemon=True).start()
        self.tcp_listener()
from threading import Lock

class Client:
    def __init__(self):
        self.udp_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.udp_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.udp_socket.bind(('', 13117))
        self.received_udp_segments = 0
        self.total_udp_segments = 0
        self.lock = Lock()  # Add a lock for thread safety

    def increment_segments(self):
        with self.lock:
            self.received_udp_segments += 1

    def listen_for_offers(self):
        while True:
            data, server_address = self.udp_socket.recvfrom(1024)
            magic_cookie, message_type, udp_port, tcp_port = struct.unpack('!IBHH', data)

            if magic_cookie == MAGIC_COOKIE and message_type == OFFER_TYPE:
                print(f"Received offer from {server_address}: UDP {udp_port}, TCP {tcp_port}")
                return server_address[0], udp_port, tcp_port

    def send_udp_request(self, server_address, udp_port, file_size):
        request_packet = create_request_packet(file_size)
        self.udp_socket.sendto(request_packet, (server_address, udp_port))

        start_time = time.time()
        while True:
            try:
                data, _ = self.udp_socket.recvfrom(2048)
                if len(data) < 21:  # Ensure minimum header size
                    print("Received an invalid UDP packet (too small). Skipping...")
                    continue

                magic_cookie, message_type, total_segments, current_segment = struct.unpack('!IBQQ', data[:21])
                if magic_cookie != MAGIC_COOKIE or message_type != PAYLOAD_TYPE:
                    print("Invalid payload received. Skipping...")
                    continue

                if not (1 <= current_segment <= total_segments):
                    print(f"Out-of-range segment: {current_segment}/{total_segments}")
                    continue

                self.received_udp_segments += 1
                if current_segment == total_segments:
                    break
            except Exception as e:
                print(f"Error receiving UDP packet: {e}")
                break

        # Ensure loss calculation only occurs once and is correct
        udp_time = (time.time() - start_time) * 1000  # ms
        udp_speed = (file_size * 8) / udp_time / 1000  # kbps
        udp_loss = max(0, 100 * (1 - (self.received_udp_segments / total_segments)))

        print(
            f"UDP transfer finished in {udp_time:.2f} milliseconds, speed: {udp_speed:.2f} kilobits/sec, loss: {udp_loss:.2f}%")

    def send_tcp_request(self, server_address, tcp_port, file_size):
        tcp_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        tcp_socket.connect((server_address, tcp_port))
        tcp_socket.sendall(f"{file_size}\n".encode())

        start_time = time.time()
        received_bytes = 0
        while True:
            data = tcp_socket.recv(1024)
            if not data:
                break
            received_bytes += len(data)
            print(f"Received {received_bytes} bytes")

        end_time = time.time()
        tcp_time = end_time - start_time
        tcp_speed = (file_size * 8) / tcp_time

        # convert tcp tcp_time to milliseconds
        tcp_time = tcp_time * 1000
        # convert tcp_speed to kilo bits/sec
        tcp_speed = tcp_speed / 1000

        print(f"TCP transfer finished in {tcp_time:.2f} milliseconds, speed: {tcp_speed:.2f} kilo bits/sec")
        tcp_socket.close()

    def run(self):
        print("Looking for a server...")
        server_address, udp_port, tcp_port = self.listen_for_offers()

        # Get file size and number of connections from the user
        file_size = int(input("Enter file size for transfer (in bytes): "))
        num_udp_connections = int(input("Enter number of UDP connections: "))
        num_tcp_connections = int(input("Enter number of TCP connections: "))

        self.total_udp_segments = file_size // 1024 + (1 if file_size % 1024 != 0 else 0)

        # Start multiple UDP connections
        print(f"Testing {num_udp_connections} UDP transfer(s)...")
        udp_threads = []
        for _ in range(num_udp_connections):
            udp_thread = threading.Thread(target=self.send_udp_request, args=(server_address, udp_port, file_size))
            udp_thread.start()
            udp_threads.append(udp_thread)

        # Start multiple TCP connections
        print(f"Testing {num_tcp_connections} TCP transfer(s)...")
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

        print("All transfers complete, listening to offer requests...")

if __name__ == "__main__":
    role = input("Are you running the server or client? (server/client): ").strip().lower()

    if role == "server":
        udp_port = int(input("Enter UDP port: "))
        tcp_port = int(input("Enter TCP port: "))
        server = Server(udp_port, tcp_port)
        server.run()

    elif role == "client":
        client = Client()
        client.run()

    else:
        print("Invalid role. Please enter 'server' or 'client'.")
