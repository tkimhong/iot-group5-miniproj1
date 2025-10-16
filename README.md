# IoT Group 5 Mini Project 1: ESP32 Smart Parking System

This IoT project implements a complete 3-slot smart parking management system using ESP32 with MicroPython. Features include automatic ID assignment, real-time monitoring via I²C LCD display, web dashboard with auto-refresh, and Telegram notifications for parking receipts.

---

# Hardware Components

- ESP32 Dev Board (flashed with MicroPython firmware)
- HC-SR04 ultrasonic sensor (entry gate detection)
- 3x IR obstacle sensors (slot occupancy detection)
- SG90 servo motor (gate mechanism)
- 16x2 LCD display with I²C backpack (PCF8574)
- Jumper wires and breadboard

---

# Software Configuration

### Prerequisites

1. ESP32 with MicroPython firmware installed
2. Wi-Fi network credentials
3. Telegram bot token from @BotFather
4. Thonny IDE or similar for file upload

## Setup

1. **Create Telegram Bot**

- Message @BotFather on Telegram
- Create new bot with `/newbot`
- Save the bot token
- Get your chat ID from @userinfobot

2. **Configure Credentials**

Update settings in `config.py`:

```py
WIFI_SSID = "YOUR_WIFI_SSID"
WIFI_PASSWORD = "YOUR_WIFI_PASSWORD"
TELEGRAM_BOT_TOKEN = "YOUR_BOT_TOKEN"
TELEGRAM_CHAT_ID = "YOUR_CHAT_ID"
```

3. **Upload Files to ESP32**

- Copy `main.py`, `config.py`, `lcd_api.py`, and `machine_i2c_lcd.py` to ESP32 root directory

4. **Connect Hardware and Run**

- Wire components according to pin configuration below
- Reset ESP32 to start the system
- Note the IP address printed in serial console
- Access web dashboard at that IP address

### Hardware Pin Configuration

| Component | ESP32 Pin | Notes |
|-----------|-----------|-------|
| Ultrasonic TRIG | GPIO 27 | Entry gate detection |
| Ultrasonic ECHO | GPIO 26 | Entry gate detection |
| Servo Signal | GPIO 16 | Gate control (PWM @ 50Hz) |
| IR Sensor S1 | GPIO 32 | Slot 1 occupancy |
| IR Sensor S2 | GPIO 35 | Slot 2 occupancy |
| IR Sensor S3 | GPIO 34 | Slot 3 occupancy |
| LCD SDA | GPIO 21 | I²C data line |
| LCD SCL | GPIO 22 | I²C clock line |

**IR Sensor Logic**: 0 = occupied (blocked), 1 = free (clear)

---

# Features

## Parking Management

- **Automatic ID Assignment**: Cars get IDs 1-3 automatically (lowest available ID)
- **Entry Gate Control**: Ultrasonic sensor detects cars, servo gate opens only if space available
- **Real-time LCD Display**: Shows available slots or "FULL" status with usage count
- **Slot Detection**: IR sensors detect when cars park/leave with debouncing (1s) and grace period (2s)

## Web Dashboard

- **Live Slot Status**: Real-time display with color coding (green=free, red=occupied)
- **Active Tickets**: Shows currently parked cars with ID, slot, time-in, and elapsed time
- **Billing History**: Recent closed tickets with duration and fee calculation
- **Auto-refresh**: Updates every 3 seconds without page reload

## Telegram Integration

- **Automatic Receipts**: Sends parking receipt when car leaves
- **Billing Information**: Includes ID, slot, duration, and calculated fee
- **Simple & Reliable**: Single GET request with basic URL encoding

## Automatic Behavior

- **ID Pool Management**: IDs 1-3 managed automatically, lowest ID assigned on parking
- **Auto-close Gate**: Gate closes 3 seconds after opening
- **Automatic Billing**: $0.50 per minute, minimum 1 minute charge
- **Wi-Fi Auto-reconnection**: Checks connection every 60 seconds

### Additional Features

- LCD update rate limiting (1.5s intervals) for stability
- Error recovery for LCD, sensors, and network
- Graceful degradation when components fail
- Memory management with garbage collection
- Static IP support (optional)

---

# Demo

**Demo Video:**

[![Demo video](https://img.youtube.com/vi/GWhinETLWaY/0.jpg)](https://www.youtube.com/watch?v=GWhinETLWaY)

_The video demonstrates:_

- Complete hardware setup and wiring
- Car arrival detection and automatic gate control
- Automatic ID assignment when cars park
- Real-time LCD display updates (free slots and usage count)
- Web dashboard with live slot status and active tickets
- Car departure detection with grace period
- Automatic billing calculation and Telegram receipt notification
- ID pool management (ID returned when car leaves)

## System Operation Flow

1. **Car Arrival**: Ultrasonic sensor detects car at gate
2. **Gate Control**: Opens if slots available, shows "FULL" if not
3. **Parking**: IR sensor detects car, assigns lowest available ID
4. **LCD Display**: Shows free slots (e.g., "Free: S1 S3" / "Used: 1/3")
5. **Departure**: IR sensor detects car leaving after 2-second grace period
6. **Billing**: Calculates fee, sends Telegram receipt, returns ID to pool

## Web Dashboard Features

_Real-time parking dashboard showing:_
- Status bar (Total/Free/Occupied counts)
- Slot panel (S1-S3) with occupancy details and elapsed time
- Active (OPEN) tickets table
- Recent (CLOSED) tickets with billing information

## Telegram Notification

_Parking receipt sent automatically:_
```
✅ Ticket CLOSED
ID: 2 | Slot: S2
Duration: 5 minutes
Fee: $2.50
```

## LCD Display

_16x2 LCD showing real-time status:_
```
Line 1: Free: S1 S3
Line 2: Used: 1/3
```

---

# System Specifications

## Timing Parameters

- **IR Debounce**: 1 second (prevents false parking/leaving triggers)
- **Leave Grace Period**: 2 seconds (confirms car actually left slot)
- **Gate Open Time**: 3 seconds (time for car to pass through)
- **LCD Update**: 1.5 seconds (regular interval + immediate on state change)
- **WiFi Check**: 60 seconds (periodic reconnection check)
- **Main Loop**: 300ms cycle time

## Billing System

- **Rate**: $0.50 per minute (configurable in config.py)
- **Minimum**: 1 minute charge
- **Calculation**: `duration = max(1, (time_out - time_in) / 60)`
- **Automatic**: Fee calculated and Telegram receipt sent on departure

## ID Assignment Logic

- **ID Pool**: [1, 2, 3] managed automatically
- **Assignment**: Lowest available ID assigned when car parks
- **Return**: ID returned to pool and sorted when car leaves
- **Prevents**: ID conflicts and gaps in numbering

---

# Installation & Usage

1. **Clone the Repository**

```bash
git clone https://github.com/tkimhong/iot-group5-miniproj1.git
```

2. **Setup Your Hardware**: Follow pin configuration table above
3. **Configure Code**: Update Wi-Fi and Telegram credentials in `config.py`
4. **Upload Files**: Copy files to ESP32 (see step 3 in Setup section above)
5. **Run System**: Reset ESP32 and monitor serial output for IP address
6. **Access Dashboard**: Navigate to ESP32's IP address in web browser

## Running the System

**Method 1 - Auto-start** (recommended):
```python
# Upload main.py file name on ESP32 for automatic startup
```

# Troubleshooting

## Common Issues

**WiFi Connection Failed**
- Check SSID/password in config.py
- Ensure ESP32 is in range

**LCD Not Working**
- Check I²C connections (SDA=21, SCL=22)
- Verify LCD I²C address (default 0x27)

**IR Sensors Not Responding**
- Verify pin connections (GPIO 32, 35, 34)
- Check sensor logic: 0=occupied, 1=free

**Telegram Not Working**
- Verify bot token and chat ID in config.py
- Check internet connection
- Test bot by messaging it first

**Gate Not Operating**
- Confirm servo pin 16 connection
- Check duty cycles: 25=closed, 75=open

---

# Project Information

**Course**: ICT 360 - Introduction to IoT

**Project Type**: Mini Project 1 - Smart Parking System

**Platform**: ESP32 with MicroPython

**Architecture**: Single-file functional design with modular functions

## File Structure

```
proj/
├── main.py                   # Main system (455 lines)
├── config.py                 # Configuration settings
├── lcd_api.py                # LCD API base class
├── machine_i2c_lcd.py        # I²C LCD implementation
├── CLAUDE.md                 # Development guide
└── README.md                 # This file
```
