#!/usr/bin/env python3
"""
TSL1401 Line Scan Camera Viewer
실시간으로 TSL1401 카메라 데이터를 표시하는 프로그램
"""

import serial
import serial.tools.list_ports
import numpy as np
import matplotlib.pyplot as plt
from matplotlib.animation import FuncAnimation
import sys
import argparse


class TSL1401Viewer:
    def __init__(self, port=None, baudrate=115200, pixels=128):
        """
        TSL1401 뷰어 초기화
        
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
            except serial.SerialException as e:
                print(f"시리얼 포트 연결 실패: {e}")
                sys.exit(1)
        else:
            print("Arduino를 찾을 수 없습니다.")
            sys.exit(1)
        
        # 그래프 설정
        self.setup_plot()
    
    def find_arduino_port(self):
        """Arduino 포트 자동 탐색"""
        ports = serial.tools.list_ports.comports()
        for port in ports:
            # Arduino 관련 키워드 확인
            if any(keyword in port.description.lower() 
                   for keyword in ['arduino', 'ch340', 'cp210', 'ftdi']):
                print(f"Arduino 발견: {port.device} - {port.description}")
                return port.device
        return None
    
    def setup_plot(self):
        """matplotlib 그래프 설정"""
        plt.style.use('dark_background')
        self.fig, (self.ax1, self.ax2) = plt.subplots(2, 1, figsize=(12, 8))
        
        # 원본 픽셀 데이터 그래프
        self.line1, = self.ax1.plot(range(self.pixels), self.pixel_data, 'g-', linewidth=2)
        self.ax1.set_ylim(0, 255)
        self.ax1.set_xlim(0, self.pixels - 1)
        self.ax1.set_title('TSL1401 Line Scan Camera - Raw Data', fontsize=14)
        self.ax1.set_xlabel('Pixel Index')
        self.ax1.set_ylabel('Intensity (0-255)')
        self.ax1.grid(True, alpha=0.3)
        
        # 히스토그램
        self.hist_data = self.ax2.bar(range(self.pixels), self.pixel_data, color='cyan', alpha=0.7)
        self.ax2.set_ylim(0, 255)
        self.ax2.set_xlim(0, self.pixels - 1)
        self.ax2.set_title('Pixel Intensity Histogram', fontsize=14)
        self.ax2.set_xlabel('Pixel Index')
        self.ax2.set_ylabel('Intensity')
        self.ax2.grid(True, alpha=0.3)
        
        # 통계 정보 텍스트
        self.stats_text = self.fig.text(0.02, 0.95, '', fontsize=10, color='yellow')
        
        plt.tight_layout()
    
    def read_serial_data(self):
        """시리얼 포트에서 데이터 읽기"""
        if self.serial_port and self.serial_port.in_waiting:
            try:
                line = self.serial_port.readline().decode('utf-8').strip()
                
                # CSV 형식 데이터 파싱
                if ',' in line:
                    values = line.split(',')
                    if len(values) == self.pixels:
                        self.pixel_data = np.array([int(v) for v in values if v.isdigit()])
                        return True
            except (ValueError, UnicodeDecodeError) as e:
                print(f"데이터 파싱 오류: {e}")
        return False
    
    def update_plot(self, frame):
        """그래프 업데이트"""
        if self.read_serial_data():
            # 라인 그래프 업데이트
            self.line1.set_ydata(self.pixel_data)
            
            # 히스토그램 업데이트
            for bar, height in zip(self.hist_data, self.pixel_data):
                bar.set_height(height)
            
            # 통계 정보 업데이트
            stats = (
                f"Min: {np.min(self.pixel_data):.0f}  "
                f"Max: {np.max(self.pixel_data):.0f}  "
                f"Mean: {np.mean(self.pixel_data):.1f}  "
                f"Std: {np.std(self.pixel_data):.1f}"
            )
            self.stats_text.set_text(stats)
        
        return self.line1, *self.hist_data, self.stats_text
    
    def start(self):
        """애니메이션 시작"""
        ani = FuncAnimation(
            self.fig, 
            self.update_plot, 
            interval=50,  # 50ms 업데이트 주기
            blit=True,
            cache_frame_data=False
        )
        
        plt.show()
    
    def close(self):
        """리소스 정리"""
        if self.serial_port:
            self.serial_port.close()


def main():
    """메인 함수"""
    parser = argparse.ArgumentParser(description='TSL1401 Line Scan Camera Viewer')
    parser.add_argument(
        '-p', '--port',
        help='시리얼 포트 (예: COM3, /dev/ttyUSB0)',
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
    viewer = TSL1401Viewer(args.port, args.baudrate, args.pixels)
    
    try:
        print("TSL1401 뷰어 시작... (종료: Ctrl+C 또는 창 닫기)")
        viewer.start()
    except KeyboardInterrupt:
        print("\n종료합니다...")
    finally:
        viewer.close()


if __name__ == "__main__":
    main()