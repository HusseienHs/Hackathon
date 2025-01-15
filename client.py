import socket
import struct
import threading
import time
from shared import create_request_packet, MAGIC_COOKIE, OFFER_TYPE, PAYLOAD_TYPE, RED, GREEN, YELLOW, RESET, CYAN

class Client:
    def __init__(self):
        self.udp_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.udp_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.udp_socket.bind(('', 13117))
        self.total_udp_segments = 0
        self.transfer_counter = 1

    def listen_for_offers(self):
        print(f"{CYAN}Client started, listening for offer requests...{RESET}")
        self.udp_socket.settimeout(1)
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

                    if len(data) < 21:
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

            udp_time = (time.time() - start_time)
            udp_speed = (file_size * 8) / udp_time
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

        end_time = time.time()
        tcp_time = (end_time - start_time)
        tcp_speed = (file_size * 8) / tcp_time

        print(f"{GREEN}TCP transfer #{self.transfer_counter} finished, total time: {tcp_time:.2f} seconds, "
              f"total speed: {tcp_speed:.2f} bits/second{RESET}")
        self.transfer_counter += 1
        tcp_socket.close()

    def run(self):
        while True:
            print(f"{CYAN}Looking for a server...{RESET}")
            try:
                server_address, udp_port, tcp_port = self.listen_for_offers()

                file_size = int(input(f"{YELLOW}Enter file size for transfer (in bytes): {RESET}"))
                num_udp_connections = int(input(f"{YELLOW}Enter number of UDP connections: {RESET}"))
                num_tcp_connections = int(input(f"{YELLOW}Enter number of TCP connections: {RESET}"))

                self.total_udp_segments = file_size // 1024 + (1 if file_size % 1024 != 0 else 0)

                print(f"{CYAN}Testing {num_udp_connections} UDP transfer(s)...{RESET}")
                udp_threads = []
                for _ in range(num_udp_connections):
                    udp_thread = threading.Thread(target=self.send_udp_request, args=(server_address, udp_port, file_size))
                    udp_thread.start()
                    udp_threads.append(udp_thread)

                print(f"{CYAN}Testing {num_tcp_connections} TCP transfer(s)...{RESET}")
                tcp_threads = []
                for _ in range(num_tcp_connections):
                    tcp_thread = threading.Thread(target=self.send_tcp_request, args=(server_address, tcp_port, file_size))
                    tcp_thread.start()
                    tcp_threads.append(tcp_thread)

                for thread in udp_threads:
                    thread.join()

                for thread in tcp_threads:
                    thread.join()

                print(f"{GREEN}All transfers complete, listening to offer requests...{RESET}")

            except Exception as e:
                print(f"{RED}Error in client: {e}{RESET}")

if __name__ == "__main__":
    client = Client()
    client.run()
