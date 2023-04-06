import serial
import time
import matplotlib.pyplot as plt

# enter the COM port number found in the Device Manager on the Windows
port_num = input("Enter Arduino's COM port number: ")
com_port = 'COM' + port_num

# initialize serial protocol
ser = serial.Serial(com_port, 9800, timeout=1)
time.sleep(2)

# array stores data from serail buffer
data = []
data_amount = 256

for i in range(data_amount):
    line = ser.readline()   # read a byte string
    if line:
        string = line.decode()  # convert the byte string to a unicode string
        num = int(string) # convert the unicode string to an int
        print(num)
        data.append(num) # add int to data list
ser.close()

# write/overwrite data to file
dataFile = open("samplingData.txt", "w")
for i in range(data_amount):
    dataFile.write(str(data[i]))
    dataFile.write("\n")
dataFile.close()

# build the plot
plt.plot(data)
plt.xlabel('Time')
plt.ylabel('Analog Input Reading')
plt.title('Analog Input Reading vs. Time')
plt.show()
