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
        self.ani = None
        
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
            # Arduino 관련 키워드 확인 (description 또는 hwid에서)
            search_text = (port.description + " " + port.hwid).lower()
            if any(keyword in search_text 
                   for keyword in ['arduino', 'ch340', 'cp210', 'ftdi', '2341:', 'acm']):
                print(f"Arduino 발견: {port.device} - {port.description} [{port.hwid}]")
                return port.device
        return None
    
    def setup_plot(self):
        """matplotlib 그래프 설정"""
        # 백엔드 설정 (headless 환경 대응)
        import matplotlib
        matplotlib.use('TkAgg')  # 또는 'Qt5Agg'
        
        plt.style.use('dark_background')
        self.fig, self.ax1 = plt.subplots(1, 1, figsize=(14, 8))
        
        # TSL1401 라인 카메라 그래프 (X축: 픽셀위치, Y축: 픽셀값)
        self.line1, = self.ax1.plot(range(self.pixels), self.pixel_data, 'g-', linewidth=2, marker='o', markersize=2)
        self.ax1.set_ylim(0, 255)
        self.ax1.set_xlim(0, self.pixels - 1)
        self.ax1.set_title('TSL1401 Line Scan Camera - Pixel Intensity vs Position', fontsize=16, color='white')
        self.ax1.set_xlabel('Pixel Position (0-127)', fontsize=12, color='white')
        self.ax1.set_ylabel('Pixel Value (0-255)', fontsize=12, color='white')
        self.ax1.grid(True, alpha=0.3)
        
        # 축 색상 설정
        self.ax1.tick_params(colors='white')
        self.ax1.spines['bottom'].set_color('white')
        self.ax1.spines['top'].set_color('white')
        self.ax1.spines['left'].set_color('white')
        self.ax1.spines['right'].set_color('white')
        
        # 통계 정보 텍스트
        self.stats_text = self.fig.text(0.02, 0.95, '', fontsize=12, color='yellow')
        
        
        plt.tight_layout()
    
    def read_serial_data(self):
        """시리얼 포트에서 데이터 읽기"""
        if self.serial_port and self.serial_port.in_waiting:
            try:
                line = self.serial_port.readline().decode('utf-8', errors='ignore').strip()
                
                # CSV 형식 데이터 파싱
                if ',' in line and not line.startswith('Sharpness'):
                    values = line.split(',')
                    # 빈 문자열 제거하고 숫자만 필터링
                    valid_values = [v for v in values if v.strip() and v.strip().isdigit()]
                    
                    if len(valid_values) >= self.pixels:
                        self.pixel_data = np.array([int(v) for v in valid_values[:self.pixels]])
                        return True
            except (ValueError, UnicodeDecodeError) as e:
                print(f"데이터 파싱 오류: {e}")
        return False
    
    def update_plot(self, frame):
        """그래프 업데이트"""
        if self.read_serial_data():
            # 라인 그래프 업데이트
            self.line1.set_ydata(self.pixel_data)
            
            mean_val = np.mean(self.pixel_data)
            
            # 통계 정보 업데이트
            stats = (
                f"Min: {np.min(self.pixel_data):.0f}  "
                f"Max: {np.max(self.pixel_data):.0f}  "
                f"Mean: {mean_val:.1f}  "
                f"Std: {np.std(self.pixel_data):.1f}  "
                f"Range: {np.max(self.pixel_data) - np.min(self.pixel_data):.0f}"
            )
            self.stats_text.set_text(stats)
            
            # Y축을 0-255로 고정
            self.ax1.set_ylim(0, 255)
        
        return [self.line1, self.stats_text]
    
    def start(self):
        """애니메이션 시작"""
        try:
            self.ani = FuncAnimation(
                self.fig, 
                self.update_plot, 
                interval=100,  # 100ms 업데이트 주기
                blit=False,    # blit=False로 변경 (안정성 향상)
                cache_frame_data=False
            )
            
            # 창 제목 설정
            manager = plt.get_current_fig_manager()
            if hasattr(manager, 'window'):
                if hasattr(manager.window, 'wm_title'):
                    manager.window.wm_title('TSL1401 Line Scan Camera Viewer')
            
            plt.show()
            
        except Exception as e:
            print(f"그래프 표시 오류: {e}")
            print("대신 콘솔 모드로 전환합니다...")
            self.console_mode()
    
    def console_mode(self):
        """GUI 실패 시 콘솔 모드로 전환"""
        import time
        print("콘솔 모드로 실행 중...")
        print("데이터 수신 대기 중... (Ctrl+C로 종료)")
        
        try:
            while True:
                if self.read_serial_data():
                    print(f"\rPixel Data - Min:{np.min(self.pixel_data):3.0f} " +
                          f"Max:{np.max(self.pixel_data):3.0f} " +
                          f"Mean:{np.mean(self.pixel_data):5.1f} " +
                          f"Std:{np.std(self.pixel_data):5.1f}", end="", flush=True)
                time.sleep(0.1)
        except KeyboardInterrupt:
            print("\n콘솔 모드 종료")
    
    def close(self):
        """리소스 정리"""
        try:
            if self.ani is not None:
                self.ani.event_source.stop()
        except:
            pass  # 이미 종료된 경우 무시
        if self.serial_port:
            self.serial_port.close()
            print("시리얼 포트가 닫혔습니다.")


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