import serial
import serial.tools.list_ports
import time
import matplotlib.pyplot as plt

'''
This code is specified for macOS Big Sur or later.

!!Making sure you already have python3 installed!!
if not check online for the installation guide

Some library are not installed default in macOS
Execute the following code in terminal:

=======================================
~ % python3 -m venv venv
~ % source venv/bin/activate
(venv) ~ % pip install pyserial
(venv) ~ % pip install matplotlib
(venv) ~ % python3 read_plot_store_macos.py
=======================================

Note that every time you start a new terminal, you need to run "source venv/bin/activate"
The last line is equvilant to the .exe file provided for windows users

The first 2 commands is to create a virtual environment and install the library, prevent conflict with homebrew installed python library
'''

# list all serial ports
ports = list(serial.tools.list_ports.comports())

# check if any serial ports are available
if not ports:
    print("No serial ports found. Please check your device connection.")
    exit()

# print all serial ports
for i, port in enumerate(ports):
    print(f"{i}: {port.device}")
choice = int(input("Select port: "))
ser = ports[choice].device

# initialize serial protocol
ser = serial.Serial(ser, 9800, timeout=1)
time.sleep(2)

# array stores data from serail buffer
data = []
data_amount = 256

for i in range(data_amount):
    line = ser.readline()                   # read a byte string
    if line:
        try:
            string = line.decode()          # convert the byte string to a unicode string
            num = int(string)               # convert the unicode string to an int
            print(num)
            data.append(num)                # add int to data list
        except ValueError:
            print(f"Invalid data: {line}")  # handle invalid data
ser.close()

# write/overwrite data to file
dataFile = open("samplingData.txt", "w")
for i in range(data_amount):
    dataFile.write(str(data[i]))
    dataFile.write("\n")
dataFile.close()
print ("Data written to samplingData.txt under current directory.")

# build the plot
plt.plot(data)
plt.xlabel('Time')
plt.ylabel('Analog Input Reading')
plt.title('Analog Input Reading vs. Time')
plt.show()
