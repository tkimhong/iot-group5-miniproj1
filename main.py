"""Smart Parking System - ESP32 MicroPython"""

from machine import Pin, PWM, SoftI2C
import time
import network
import socket
import urequests
import gc
from machine_i2c_lcd import I2cLcd

# Configuration
try:
    from config import WIFI_SSID, WIFI_PASSWORD, TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID
    from config import CAR_DETECTION_DISTANCE, PRICING_PER_MINUTE
    from config import STATIC_IP, SUBNET_MASK, GATEWAY, DNS_SERVER
except ImportError:
    WIFI_SSID = 'YOUR_WIFI_SSID'
    WIFI_PASSWORD = 'YOUR_WIFI_PASSWORD'
    TELEGRAM_BOT_TOKEN = 'YOUR_BOT_TOKEN'
    TELEGRAM_CHAT_ID = 'YOUR_CHAT_ID'
    CAR_DETECTION_DISTANCE = 20
    PRICING_PER_MINUTE = 0.5
    STATIC_IP = None
    SUBNET_MASK = "255.255.255.0"
    GATEWAY = "192.168.1.1"
    DNS_SERVER = "8.8.8.8"
    SLOT_IR_PINS = [32, 34, 35]

# LCD Setup
I2C_ADDR = 0x27
I2C_ROWS = 2
I2C_COLS = 16
i2c = SoftI2C(scl=Pin(22), sda=Pin(21), freq=400000)
lcd = I2cLcd(i2c, I2C_ADDR, I2C_ROWS, I2C_COLS)

# Hardware Pins
SLOT_IR_PINS = [32, 35, 34]  # S1, S2, S3 (0=occupied, 1=free)
ULTRASONIC_TRIG = Pin(27, Pin.OUT)
ULTRASONIC_ECHO = Pin(26, Pin.IN)
SERVO = PWM(Pin(16), freq=50)

# Data Structures
slots = [{
    'occupied': False,
    'id': 0,
    'time_in': 0,
    'last_ir_state': 1,
    'state_change_time': 0
} for _ in range(3)]
free_ids = [1, 2, 3]
closed_tickets = []

# LCD Timing
last_lcd_update = 0
LCD_UPDATE_INTERVAL = 1500
lcd_needs_update = True
lcd_error_count = 0


def get_distance():
    """Measure distance with HC-SR04 (returns cm or None)"""
    try:
        ULTRASONIC_TRIG.value(0)
        time.sleep_us(2)
        ULTRASONIC_TRIG.value(1)
        time.sleep_us(10)
        ULTRASONIC_TRIG.value(0)

        timeout = time.ticks_us() + 30000
        while ULTRASONIC_ECHO.value() == 0:
            if time.ticks_us() > timeout:
                return None
        t_echo_start = time.ticks_us()

        timeout = time.ticks_us() + 30000
        while ULTRASONIC_ECHO.value() == 1:
            if time.ticks_us() > timeout:
                return None
        t_echo_end = time.ticks_us()

        duration = time.ticks_diff(t_echo_end, t_echo_start)
        distance = (duration * 0.0343) / 2
        return distance
    except:
        return None

def open_gate():
    SERVO.duty(75)

def close_gate():
    SERVO.duty(25)

def show_lcd():
    """Update LCD (rate-limited 1.5s)"""
    global last_lcd_update, lcd_needs_update, lcd_error_count
    current_time = time.ticks_ms()

    if not lcd_needs_update and time.ticks_diff(current_time, last_lcd_update) < LCD_UPDATE_INTERVAL:
        return

    if lcd_error_count > 5:
        return

    try:
        lcd.clear()
        time.sleep_ms(100)

        free = [f"S{i+1}" for i, slot in enumerate(slots) if not slot['occupied']]
        occupied_count = 3 - len(free)

        lcd.move_to(0, 0)
        if not free:
            lcd.putstr('PARKING FULL')
        else:
            free_str = 'Free: ' + ' '.join(free)
            lcd.putstr(free_str[:16])

        time.sleep_ms(50)

        lcd.move_to(0, 1)
        lcd.putstr(f'Used: {occupied_count}/3')

        last_lcd_update = current_time
        lcd_needs_update = False
        lcd_error_count = 0

    except Exception as e:
        lcd_error_count += 1
        if lcd_error_count <= 3:
            print(f"LCD error: {e}")
        time.sleep_ms(200)

def send_telegram_notification(ticket):
    """Simple Telegram notification (single GET request)"""
    try:
        message = f"✅ Ticket CLOSED\nID: {ticket['id']} Slot: S{ticket['slot']+1}\nDuration: {ticket['duration']} minutes\nFee: ${ticket['fee']:.2f}"
        encoded_message = message.replace('\n', '%0A').replace(' ', '%20').replace(':', '%3A').replace('$', '%24')
        url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage?chat_id={TELEGRAM_CHAT_ID}&text={encoded_message}"
        r = urequests.get(url, timeout=8)
        if r.status_code == 200:
            print(f"✅ Telegram sent for ID {ticket['id']}")
        else:
            print(f"❌ Telegram failed for ID {ticket['id']} (status: {r.status_code})")
        r.close()
    except Exception as e:
        print(f"❌ Telegram error: {e}")
    finally:
        gc.collect()

def ensure_wifi_connection():
    """Reconnect WiFi if disconnected"""
    global sta_if
    if not sta_if.isconnected():
        print("WiFi disconnected, reconnecting...")
        sta_if.connect(WIFI_SSID, WIFI_PASSWORD)
        time.sleep(2)

def handle_entry():
    """Handle gate control"""
    distance = get_distance()
    if distance and distance < CAR_DETECTION_DISTANCE:
        show_lcd()
        if all(slot['occupied'] for slot in slots):
            close_gate()
            print("Car detected but parking FULL")
        else:
            open_gate()
            print(f"Gate opened for car, distance: {distance:.1f}cm")
            time.sleep(3)
            close_gate()

def handle_slot_logic():
    """Process IR sensors (1s debounce, 2s grace period)"""
    now = time.time()
    current_time_ms = time.ticks_ms()

    for i, pin_num in enumerate(SLOT_IR_PINS):
        ir_pin = Pin(pin_num, Pin.IN)
        current_reading = ir_pin.value()
        slot = slots[i]

        if current_reading != slot['last_ir_state']:
            slot['last_ir_state'] = current_reading
            slot['state_change_time'] = current_time_ms

        time_since_change = time.ticks_diff(current_time_ms, slot['state_change_time'])

        if time_since_change >= 1000:
            if current_reading == 0 and not slot['occupied']:
                if free_ids:
                    new_id = min(free_ids)
                    free_ids.remove(new_id)
                    slot['occupied'] = True
                    slot['id'] = new_id
                    slot['time_in'] = now
                    lcd_needs_update = True
                    print(f"Car ID {new_id} parked in S{i+1}")

            elif current_reading == 1 and slot['occupied']:
                if time_since_change >= 2000:
                    old_id = slot['id']
                    time_out = now
                    duration = max(1, int((now - slot['time_in']) / 60))
                    fee = duration * PRICING_PER_MINUTE
                    ticket = {'id': old_id, 'slot': i, 'duration': duration, 'fee': fee, 'time_out': time_out}
                    closed_tickets.append(ticket)

                    time.sleep(2)
                    send_telegram_notification(ticket)

                    slot['occupied'] = False
                    slot['id'] = 0
                    slot['time_in'] = 0
                    free_ids.append(old_id)
                    free_ids.sort()
                    lcd_needs_update = True
                    print(f"Car ID {old_id} left S{i+1} - {duration}min, ${fee:.2f}")

def create_dashboard_html():
    """Generate HTML dashboard"""
    free_count = sum(1 for slot in slots if not slot['occupied'])
    occupied_count = 3 - free_count
    status = 'FULL' if occupied_count == 3 else 'Available'

    html = f"""<html><head>
<title>Smart Parking Dashboard</title>
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta http-equiv="refresh" content="3">
<style>
body{{font-family: Arial; margin: 20px; background: #f5f5f5;}}
.header{{background: #2c3e50; color: white; padding: 15px; text-align: center; margin-bottom: 20px;}}
.status-bar{{background: #34495e; color: white; padding: 15px; margin: 10px 0; text-align: center; font-size: 18px;}}
.panel{{background: white; margin: 15px 0; padding: 20px; border-radius: 5px;}}
.slots{{display: flex; gap: 15px; margin: 20px 0;}}
.slot{{flex: 1; padding: 15px; text-align: center; border-radius: 8px; border: 2px solid;}}
.free{{background: #e8f5e8; border-color: #27ae60;}}
.occupied{{background: #ffebee; border-color: #e74c3c;}}
table{{width: 100%; border-collapse: collapse; margin: 10px 0;}}
th, td{{padding: 8px; border: 1px solid #ddd; text-align: center;}}
th{{background: #34495e; color: white;}}
.occupied-row{{background: #ffebee;}}
</style>
</head><body>

<div class="header">
<h1>Smart Parking Dashboard</h1>
</div>

<div class="status-bar">
<strong>Total: 3 | Free: {free_count} | Occupied: {occupied_count} | Status: {status}</strong>
</div>

<div class="panel">
<h3>Slot Panel (S1-S3)</h3>
<div class="slots">"""

    for i, slot in enumerate(slots):
        slot_class = "occupied" if slot['occupied'] else "free"
        if slot['occupied']:
            elapsed = int(time.time() - slot['time_in']) if slot['time_in'] else 0
            time_in = time.localtime(slot['time_in']) if slot['time_in'] else None
            time_str = f"{time_in[3]:02d}:{time_in[4]:02d}:{time_in[5]:02d}" if time_in else ""
            elapsed_min = elapsed // 60
            elapsed_sec = elapsed % 60

            slot_content = f"""<strong>S{i+1}</strong><br>
<strong>Occupied</strong><br>
ID: {slot['id']}<br>
Time-In: {time_str}<br>
Elapsed: {elapsed_min}m {elapsed_sec}s"""
        else:
            slot_content = f"<strong>S{i+1}</strong><br><strong>Free</strong>"

        html += f'<div class="slot {slot_class}">{slot_content}</div>'

    html += """</div>
</div>

<div class="panel">
<h3>Active (OPEN) Tickets</h3>
<table>
<tr><th>ID</th><th>Slot</th><th>Time-In</th><th>Elapsed</th></tr>"""

    active_found = False
    for i, slot in enumerate(slots):
        if slot['occupied'] and slot['id']:
            elapsed = int(time.time() - slot['time_in']) if slot['time_in'] else 0
            time_in = time.localtime(slot['time_in']) if slot['time_in'] else None
            time_str = f"{time_in[3]:02d}:{time_in[4]:02d}:{time_in[5]:02d}" if time_in else ""
            elapsed_min = elapsed // 60
            elapsed_sec = elapsed % 60

            html += f'<tr class="occupied-row"><td>{slot["id"]}</td><td>S{i+1}</td><td>{time_str}</td><td>{elapsed_min}m {elapsed_sec}s</td></tr>'
            active_found = True

    if not active_found:
        html += '<tr><td colspan="4">No active tickets</td></tr>'

    html += """</table>
</div>

<div class="panel">
<h3>Recent (CLOSED) Tickets</h3>
<table>
<tr><th>ID</th><th>Slot</th><th>Duration</th><th>Fee</th><th>Time-Out</th></tr>"""

    if closed_tickets:
        for ticket in closed_tickets[-5:]:
            time_out = time.localtime(ticket.get('time_out', time.time()))
            time_out_str = f"{time_out[3]:02d}:{time_out[4]:02d}:{time_out[5]:02d}"
            html += f'<tr><td>{ticket["id"]}</td><td>S{ticket["slot"]+1}</td><td>{ticket["duration"]} min</td><td>${ticket["fee"]:.2f}</td><td>{time_out_str}</td></tr>'
    else:
        html += '<tr><td colspan="5">No recent tickets</td></tr>'

    html += """</table>
</div>

<p style="text-align: center; color: #7f8c8d; font-size: 12px;">
Auto-refresh every 3 seconds
</p>

</body></html>"""
    return html

def start_web_server():
    """HTTP server on port 80"""
    print("Starting web server...")

    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        s.bind(('', 80))
        s.listen(5)
        print("Web server listening on port 80")

        while True:
            try:
                conn, addr = s.accept()
                request = conn.recv(1024)
                request = str(request)

                response = create_dashboard_html()

                conn.send('HTTP/1.1 200 OK\n')
                conn.send('Content-Type: text/html\n')
                conn.send('Connection: close\n\n')
                conn.sendall(response)
                conn.close()

            except Exception as e:
                try:
                    conn.close()
                except:
                    pass

    except Exception as e:
        print(f"Web server error: {e}")

def main():
    """Initialize and run main loop"""
    global sta_if
    print("=" * 40)
    print("  SMART PARKING SYSTEM")
    print("=" * 40)

    # WiFi
    sta_if = network.WLAN(network.STA_IF)
    sta_if.active(True)
    print(f"Connecting to {WIFI_SSID}...")
    sta_if.connect(WIFI_SSID, WIFI_PASSWORD)

    timeout = 15
    while not sta_if.isconnected() and timeout > 0:
        print(".", end="")
        time.sleep(1)
        timeout -= 1

    if not sta_if.isconnected():
        print("\nWiFi connection failed!")
        return

    if STATIC_IP:
        try:
            sta_if.ifconfig((STATIC_IP, SUBNET_MASK, GATEWAY, DNS_SERVER))
            print(f'\nStatic IP set: {STATIC_IP}')
        except Exception as e:
            print(f'\nStatic IP failed: {e}')
    else:
        print(f'\nDHCP IP: {sta_if.ifconfig()[0]}')

    ip_address = sta_if.ifconfig()[0]
    print(f'Dashboard: http://{ip_address}')
    print("=" * 40)

    # LCD
    try:
        show_lcd()
        print("LCD initialized")
    except Exception as e:
        print(f"LCD init error: {e}")

    # Web Server
    import _thread
    try:
        _thread.start_new_thread(start_web_server, ())
        print("Web server started")
    except Exception as e:
        print(f"Web server start error: {e}")

    # Main Loop
    error_count = 0
    loop_count = 0
    last_wifi_check = 0
    print("Starting main loop...")

    while True:
        try:
            current_time = time.ticks_ms()

            if time.ticks_diff(current_time, last_wifi_check) > 60000:
                ensure_wifi_connection()
                last_wifi_check = current_time

            handle_entry()
            handle_slot_logic()
            show_lcd()

            error_count = 0
            time.sleep(0.3)
            loop_count += 1

            if loop_count % 100 == 0:
                free_count = sum(1 for slot in slots if not slot['occupied'])
                print(f"Status: {free_count} free slots")

        except Exception as e:
            error_count += 1
            if error_count <= 5:
                print(f"Loop error: {e}")

            if error_count > 20:
                print("System restart needed")
                time.sleep(10)
                error_count = 0

            time.sleep(1)

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\nSystem stopped by user")
    except Exception as e:
        print(f"System crash: {e}")
        time.sleep(5)
