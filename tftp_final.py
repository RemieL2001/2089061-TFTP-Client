#!/usr/bin/python3
''’
사용법
python tftp_final.py ip주소 [-p 포트번호] (get/put) 파일이름
'''
import os
import sys
import socket
import argparse
from struct import pack, unpack
import time

DEFAULT_PORT = 69
BLOCK_SIZE = 512     #블록 사이즈
DEFAULT_TRANSFER_MODE = 'octet'
TIMEOUT = 5    

OPCODE = {'RRQ': 1, 'WRQ': 2, 'DATA': 3, 'ACK': 4, 'ERROR': 5}
MODE = {'netascii': 1, 'octet': 2, 'mail': 3}

ERROR_CODE = {
    0: "Not defined, see error message (if any).",
    1: "File not found.",
    2: "Access violation.",
    3: "Disk full or allocation exceeded.",
    4: "Illegal TFTP operation.",
    5: "Unknown transfer ID.",
    6: "File already exists.",
    7: "No such user."
}

def send_rrq(filename, mode):
    format = f'>h{len(filename)}sB{len(mode)}sB'
    rrq_message = pack(format, OPCODE['RRQ'], bytes(filename, 'utf-8'), 0, bytes(mode, 'utf-8'), 0)
    sock.sendto(rrq_message, server_address)

def send_wrq(filename, mode):
    format = f'>h{len(filename)}sB{len(mode)}sB'
    wrq_message = pack(format, OPCODE['WRQ'], bytes(filename, 'utf-8'), 0, bytes(mode, 'utf-8'), 0)
    sock.sendto(wrq_message, server_address)

def send_ack(seq_num, server):
    format = f'>hh'
    ack_message = pack(format, OPCODE['ACK'], seq_num)
    sock.sendto(ack_message, server)

#지정된 시간 내 응답이 없으면 타임아웃웃
def receive_with_timeout(sock, bufsize): 
    sock.settimeout(TIMEOUT)
    try:
        return sock.recvfrom(bufsize)
    except socket.timeout:
        return None, None

#파일 다운로드
def get_file(filename, mode):
    send_rrq(filename, mode)
    with open(filename, 'wb') as file:
        expected_block_number = 1	
        retries = 0
        while retries < 3:
            data, server_new_socket = receive_with_timeout(sock, 516)
            if data is None:	#timeout 발생 시
                print("Timeout occurred. Retrying...")
                retries += 1
                send_rrq(filename, mode)	#rrq 재전송
                continue

            retries = 0
            opcode = unpack('>h', data[:2])[0]
            if opcode == OPCODE['DATA']:
                block_number = unpack('>h', data[2:4])[0]
                if block_number == expected_block_number:
                    send_ack(block_number, server_new_socket)
                    file_block = data[4:]
                    file.write(file_block)
                    expected_block_number += 1	#다음 블록 번호 증가
                    print(f"Received block {block_number}")
                else:
                    send_ack(block_number, server_new_socket)

                if len(file_block) < BLOCK_SIZE:
                    print("파일 다운로드 완료!")
                    return True
            elif opcode == OPCODE['ERROR']:
                error_code = unpack('>h', data[2:4])[0]
                print(f"Error: {ERROR_CODE[error_code]}")
                return False
            else:
                print(f"Unexpected opcode: {opcode}")
                return False
        print("다운로드에 실패했습니다.")
        return False
        
#파일 업로드
def put_file(filename, mode):
    send_wrq(filename, mode)
    with open(filename, 'rb') as file:
        block_number = 0
        retries = 0
        while retries < 3:
            data, server_new_socket = receive_with_timeout(sock, 516)
            #타임아웃 발생시
            if data is None:
                print("Timeout occurred. Retrying...")
                retries += 1
                if block_number == 0:
                    send_wrq(filename, mode)
                else:
                    file.seek((block_number - 1) * BLOCK_SIZE)	#해당 블록 위치로 이동
                    data_to_send = file.read(BLOCK_SIZE)
                    send_data(block_number, data_to_send, server_new_socket)
                continue

            retries = 0
            opcode = unpack('>h', data[:2])[0]
            if opcode == OPCODE['ACK']:
                ack_block_number = unpack('>h', data[2:4])[0]
                if ack_block_number == block_number:
                    block_number += 1
                    data_to_send = file.read(BLOCK_SIZE)
                    if data_to_send:
                        send_data(block_number, data_to_send, server_new_socket)
                        print(f"Sent block {block_number}")
                    else:
                        print("파일 업로드 완료!")
                        return True
            elif opcode == OPCODE['ERROR']:
                error_code = unpack('>h', data[2:4])[0]
                print(f"Error: {ERROR_CODE[error_code]}")
                return False
            else:
                print(f"Unexpected opcode: {opcode}")
                return False
        print("전송에 실패했습니다.")
        return False

def send_data(seq_num, data, server):
    format = f'>hh{len(data)}s'
    data_message = pack(format, OPCODE['DATA'], seq_num, data)
    sock.sendto(data_message, server)
    print(f"Sent block {seq_num}")

parser = argparse.ArgumentParser(description='TFTP client program')
parser.add_argument('host', help="Server IP address", type=str)
parser.add_argument('operation', help="get or put a file", type=str)
parser.add_argument('filename', help="name of file to transfer", type=str)
parser.add_argument("-p", "--port", help="server port number", type=int, default=DEFAULT_PORT)
args = parser.parse_args()

server_ip = args.host
server_port = args.port
server_address = (server_ip, server_port)
sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)

mode = DEFAULT_TRANSFER_MODE
operation = args.operation.lower()
filename = args.filename

success = False
if operation == 'get':
    success = get_file(filename, mode)
elif operation == 'put':
    success = put_file(filename, mode)
else:
    print("잘못된 작업입니다. 'get' 또는 'put'을 사용하세요.")

sock.close()
sys.exit(0 if success else 1)
