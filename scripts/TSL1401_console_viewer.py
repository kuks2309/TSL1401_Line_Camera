#!/usr/bin/env python3
"""
TSL1401 Line Scan Camera Console Viewer
콘솔에서 TSL1401 카메라 데이터를 실시간으로 표시하는 프로그램
"""

import serial
import serial.tools.list_ports
import numpy as np
import sys
import time
import argparse


class TSL1401ConsoleViewer:
    def __init__(self, port=None, baudrate=115200, pixels=128):
        """
        TSL1401 콘솔 뷰어 초기화
        
        Args:
            port: 시리얼 포트 (None이면 자동 탐색)
            baudrate: 통신 속도
            pixels: 픽셀 수
        """
        self.baudrate = baudrate
        self.pixels = pixels
        self.pixel_data = np.zeros(pixels)
        self.serial_port = None
        
        # 시리얼 포트 연결
        if port is None:
            port = self.find_arduino_port()
        
        if port:
            try:
                self.serial_port = serial.Serial(port, baudrate, timeout=0.1)
                print(f"연결됨: {port} @ {baudrate} bps")
                time.sleep(2)  # Arduino 리셋 대기
            except serial.SerialException as e:
                print(f"시리얼 포트 연결 실패: {e}")
                sys.exit(1)
        else:
            print("Arduino를 찾을 수 없습니다.")
            sys.exit(1)
    
    def find_arduino_port(self):
        """Arduino 포트 자동 탐색"""
        ports = serial.tools.list_ports.comports()
        for port in ports:
            # Arduino 관련 키워드 확인
            if any(keyword in port.description.lower() 
                   for keyword in ['arduino', 'ch340', 'cp210', 'ftdi', 'acm']):
                print(f"Arduino 발견: {port.device} - {port.description}")
                return port.device
        return None
    
    def read_serial_data(self):
        """시리얼 포트에서 데이터 읽기"""
        if self.serial_port and self.serial_port.in_waiting:
            try:
                line = self.serial_port.readline().decode('utf-8').strip()
                
                # CSV 형식 데이터 파싱
                if ',' in line and not line.startswith('Sharpness'):
                    values = line.split(',')
                    # 빈 문자열 제거하고 숫자만 필터링
                    valid_values = [v for v in values if v.strip() and v.strip().isdigit()]
                    
                    if len(valid_values) >= self.pixels:
                        self.pixel_data = np.array([int(v) for v in valid_values[:self.pixels]])
                        return True
            except (ValueError, UnicodeDecodeError) as e:
                pass  # 조용히 넘어가기
        return False
    
    def create_line_graph(self, data, width=128, height=20):
        """TSL1401 라인 카메라용 그래프 생성 (X축: 픽셀위치, Y축: 픽셀값)"""
        if len(data) == 0:
            return []
        
        max_val = max(data) if max(data) > 0 else 255
        min_val = min(data)
        
        # 컬러 코드
        colors = {
            'red': '\033[91m',
            'green': '\033[92m', 
            'yellow': '\033[93m',
            'blue': '\033[94m',
            'magenta': '\033[95m',
            'cyan': '\033[96m',
            'white': '\033[97m',
            'gray': '\033[90m',
            'reset': '\033[0m'
        }
        
        chart = []
        
        # Y축 라벨과 그래프
        for row in range(height, 0, -1):
            # Y축 값 계산 (픽셀 값 범위 0~255)
            y_val = int((row / height) * 255)
            line = f"{colors['gray']}{y_val:3d}│{colors['reset']}"
            
            # 각 픽셀 위치에 대해 그래프 그리기
            for pixel_pos in range(len(data)):
                pixel_value = data[pixel_pos]
                
                # 현재 행의 높이와 픽셀값 비교
                normalized_pixel_height = int((pixel_value / 255) * height)
                
                if normalized_pixel_height >= row:
                    # 픽셀값에 따른 색상 선택
                    intensity = pixel_value / 255
                    if intensity > 0.8:
                        color = colors['red']      # 높은 강도: 빨강
                    elif intensity > 0.6:
                        color = colors['yellow']   # 중상 강도: 노랑
                    elif intensity > 0.4:
                        color = colors['green']    # 중간 강도: 초록
                    elif intensity > 0.2:
                        color = colors['cyan']     # 중하 강도: 시안
                    else:
                        color = colors['blue']     # 낮은 강도: 파랑
                    
                    if normalized_pixel_height == row:
                        # 정확한 높이에서는 점으로 표시
                        line += f"{color}●{colors['reset']}"
                    else:
                        # 그 위쪽은 수직선으로 표시
                        line += f"{color}│{colors['reset']}"
                else:
                    line += " "
            
            chart.append(line)
        
        # X축 (하단 경계선)
        x_axis_line = f"{colors['gray']}  0└"
        for i in range(width):
            x_axis_line += "─"
        chart.append(x_axis_line + colors['reset'])
        
        # X축 픽셀 위치 라벨
        x_labels = "    "
        for i in range(0, width, 16):
            if i == 0:
                x_labels += f"{colors['gray']}{i:3d}{colors['reset']}"
            else:
                x_labels += f"{colors['gray']}{'':13}{i:3d}{colors['reset']}"
        chart.append(x_labels)
        
        # X축 제목
        chart.append(f"{colors['cyan']}    Pixel Position (0-{width-1}){colors['reset']}")
        
        return chart
    
    def display_data(self):
        """데이터 표시"""
        # 화면 지우기
        print("\033[2J\033[H", end="")
        
        # 헤더 (컬러)
        print("\033[96m" + "┌" + "─" * 78 + "┐\033[0m")
        print("\033[96m│\033[97m" + " TSL1401 Line Scan Camera - Real-time Data".center(78) + "\033[96m│\033[0m")
        print("\033[96m└" + "─" * 78 + "┘\033[0m")
        print()
        
        if len(self.pixel_data) > 0:
            # 통계 정보 (컬러 박스)
            min_val = np.min(self.pixel_data)
            max_val = np.max(self.pixel_data)
            mean_val = np.mean(self.pixel_data)
            std_val = np.std(self.pixel_data)
            
            print("\033[94m┌─ Statistics ─────────────────────────────────────────────────────────────┐\033[0m")
            print(f"\033[94m│\033[0m \033[91mMin:\033[97m {min_val:6.1f}\033[0m   " +
                  f"\033[92mMax:\033[97m {max_val:6.1f}\033[0m   " +
                  f"\033[93mMean:\033[97m {mean_val:6.1f}\033[0m   " +
                  f"\033[95mStd:\033[97m {std_val:6.1f}\033[0m \033[94m│\033[0m")
            print("\033[94m└──────────────────────────────────────────────────────────────────────────┘\033[0m")
            print()
            
            # Y축 제목
            print(f"\033[95mPixel Value (0-255)\033[0m")
            print("\033[90m     ↑\033[0m")
            
            # 라인 그래프 (X축: 픽셀위치, Y축: 픽셀값)
            chart = self.create_line_graph(self.pixel_data, width=self.pixels, height=18)
            for line in chart:
                print(line)
            
            print()
            
            # 히트맵 형태로 원본 데이터 표시
            print("\033[94m┌─ Intensity Heatmap (Pixel 0-127) ───────────────────────────────────────┐\033[0m")
            
            # 데이터를 4행으로 나누어 표시
            rows = 4
            cols_per_row = self.pixels // rows
            
            for row in range(rows):
                print(f"\033[94m│\033[90m{row*cols_per_row:3d}-{min((row+1)*cols_per_row-1, self.pixels-1):3d}:\033[0m ", end="")
                start_idx = row * cols_per_row
                end_idx = min(start_idx + cols_per_row, self.pixels)
                
                for i in range(start_idx, end_idx):
                    intensity = self.pixel_data[i] / 255  # 0-255 범위로 정규화
                    
                    # 히트맵 컬러
                    if intensity > 0.9:
                        color = "\033[41m"  # 빨간 배경
                    elif intensity > 0.7:
                        color = "\033[43m"  # 노란 배경
                    elif intensity > 0.5:
                        color = "\033[42m"  # 초록 배경
                    elif intensity > 0.3:
                        color = "\033[46m"  # 시안 배경
                    elif intensity > 0.1:
                        color = "\033[44m"  # 파란 배경
                    else:
                        color = "\033[40m"  # 검은 배경
                    
                    print(f"{color} \033[0m", end="")
                
                # 줄 맞추기
                remaining = cols_per_row - (end_idx - start_idx)
                print(" " * remaining, end="")
                print(f" \033[94m│\033[0m")
            
            print("\033[94m└──────────────────────────────────────────────────────────────────────────┘\033[0m")
            
            # 컬러 범례
            print("\033[90mColor Legend: \033[40m Low \033[0m\033[44m ░ \033[0m\033[46m ▒ \033[0m\033[42m ▓ \033[0m\033[43m █ \033[0m\033[41m High \033[0m")
            
        else:
            print("\033[93m⏳ 데이터 수신 대기 중...\033[0m")
        
        print()
        print("\033[90m💡 종료: Ctrl+C\033[0m")
    
    def start(self):
        """뷰어 시작"""
        print("TSL1401 콘솔 뷰어 시작...")
        print("데이터 수신 대기 중...")
        
        try:
            while True:
                if self.read_serial_data():
                    self.display_data()
                time.sleep(0.1)  # 100ms 업데이트 주기
                
        except KeyboardInterrupt:
            print("\n\n프로그램을 종료합니다...")
        finally:
            self.close()
    
    def close(self):
        """리소스 정리"""
        if self.serial_port:
            self.serial_port.close()
            print("시리얼 포트가 닫혔습니다.")


def main():
    """메인 함수"""
    parser = argparse.ArgumentParser(description='TSL1401 Line Scan Camera Console Viewer')
    parser.add_argument(
        '-p', '--port',
        help='시리얼 포트 (예: COM3, /dev/ttyUSB0, /dev/ttyACM0)',
        default=None
    )
    parser.add_argument(
        '-b', '--baudrate',
        type=int,
        default=115200,
        help='통신 속도 (기본값: 115200)'
    )
    parser.add_argument(
        '-n', '--pixels',
        type=int,
        default=128,
        help='픽셀 수 (기본값: 128)'
    )
    
    args = parser.parse_args()
    
    # 뷰어 실행
    viewer = TSL1401ConsoleViewer(args.port, args.baudrate, args.pixels)
    viewer.start()


if __name__ == "__main__":
    main()