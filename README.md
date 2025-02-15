# UDP and TCP File Transfer Client-Server 🚀

A simple file transfer system using UDP and TCP protocols. The client and server communicate to send and receive files with custom protocols, supporting multiple concurrent file transfer requests and evaluating performance. 📡

## Team 👨🏻‍💻
 
- Husseien Hasanin Id : 213971054.
- Fadi Zoabi Id : 214026775.

## Features ⭐
- **UDP and TCP File Transfer**: Transfer files via UDP and TCP protocols.
- **Multiple Connections**: Simultaneous UDP and TCP transfers.
- **Performance Metrics**: Reports transfer time, speed, and packet loss for UDP, and transfer time and speed for TCP.

## Requirements ⚙️
- Python 3.6+
- Built-in modules: `struct`, `threading`, `socket`

## Installation 🛠️
1. Clone the repository:
   ```bash
   git clone https://github.com/HusseienHs/Hackathon.git

## Usage 💻

### Run the Server
```bash
python server.py
```

### Run the Client 
```bash
python client.py
```
Follow the prompts to specify file size and number of connections for testing.

## Code Overview 📝
- **client.py**: Handles UDP and TCP transfer requests and performance reporting.
- **server.py**: Listens for client requests and handles file transfer via UDP/TCP.
- **shared.py**: Utility functions for packet creation.
