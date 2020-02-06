import time
import datetime
import threading
import serial
import numpy as np
import matplotlib.pyplot as plt

'''
Goal: Reconstruct and debug Serial Communication with Runge mikron 31

Objectives
1. Debug Signal Recording
    - Test time out?
    - Sort out bad Signal readings
2. Debug Plotting
    - Plot normally
    - Plot in the background
3. Delete zeros in first line of rng_data
'''

# Name of serial port
port_name: str = '/dev/tty.usbmodem143201'
# Open serial port
rng = serial.Serial(port=port_name, timeout=1)

# Flag to control Thread <Record>
exitFlag = False

# Array for signal data
rng_data = np.array([0]*5)
# List for all other responses
rng_log = [datetime.datetime.today()]
# Time window (s) for live plot
view_t = 60 * 30


'''
Initialize Runge Detector
'''


# Define query Function
def query(cmd='STATUS?'):
    # Append ending character '\r'
    cmd_full = ''.join([cmd, '\r'])
    # Send command
    rng.write(bytearray(cmd_full, 'ascii'))
    # Read response from device
    rsp_full = rng.read_until(b'\r')
    return rsp_full

# Query device information and status
print(''.join(['\n', '-'*23, '\nMikron 31 Device Status\n', '-'*23, '\n']))
# List of commands
rng_init_queries = ['IDENTIFY?', 'INFO?', 'STATUS?', 'MOD1_INFO?', 'MOD2_INFO?', 'STOP']
# Iterate through commands
for i in rng_init_queries:
    rsp_full = query(i).decode()
    # Print received command
    print(rsp_full)
    # Append to log file
    rng_log.append(rsp_full.replace('\r', ''))
    # Save Wavelengths
    if rsp_full.startswith('MOD1_INFO:'):
        Wl1 = rsp_full.split(',')[2] + ' nm'
    if rsp_full.startswith('MOD2_INFO:'):
        Wl2 = rsp_full.split(',')[2] + ' nm'


'''
Define Thread Functions
'''

# Function recording signal data (Runge mikron signal format)
def rng_record():
    global rng_data
    print('Started Thread <Signal Recording>')
    while not exitFlag:
        # Read for response from device
        rng_sig_raw = rng.read_until(b'\r').decode()
        if rng_sig_raw.startswith('SIG:'):
            for r in (('SIG:', ''), ('\r', '')):
                rng_sig_raw = rng_sig_raw.replace(*r)
            try:
                # Convert to list of floats
                rng_sig = [float(i) for i in rng_sig_raw.split(',')]
                if len(rng_sig) == 5:
                    # Add row to data set
                    rng_data = np.vstack((rng_data, np.array([rng_sig])))
            except ValueError:
                print('Unknown signal format: ' + rng_sig_raw)
        else:
            rng_sig = rng_sig_raw.replace('\r', '')
            time_stamp = datetime.datetime.today()
            rng_log.append(time_stamp)
            rng_log.append(rng_sig)
            if rng_sig.startswith('AZ:'):
                print(rng_sig)
            elif rng_sig.startswith('STOP:'):
                print(rng_sig)
    print('Stopped Thread <Signal Recording>')


# Function accepting user inputs to control device
def rng_control():
    global exitFlag
    print('Started Thread <Control>')
    while True:
        text = input('Prompt: ')
        # Append ending character '\r'
        cmd_full = ''.join([text, '\r'])
        # Send command
        rng.write(bytearray(cmd_full, "ascii"))
        if text == 'SIG_START':
            t1.start()
            print('Type STOP to abort:')
        elif text == 'STOP':
            exitFlag = True
            time.sleep(1)
            break
        elif text == 'AZ':
            print(text)
        else:
            print('Again ... ')
    print('Stopped Thread <Control>')

'''
Initialize Plot
---------------
'''
# Turn interactive mode on
plt.ion()
# Create new empty figure
fig = plt.figure(figsize=[14, 7])
# Create subplot
ax = plt.subplot(1,1,1)
fig.canvas.draw()
line1, = plt.plot(0, 0, '-r', linewidth=0.5)
line2, = plt.plot(0, 0,'-b', linewidth=0.5)
# Figure labels
plt.suptitle('Runge mikron 31: Absorbance')
plt.xlabel('Time (s)')
plt.ylabel('Absorbance (mAU)')
plt.legend((line1, line2), (Wl1, Wl2), loc=2, ncol=2, frameon=False)
plt.grid()
plt.show()



'''
Start Threads
-------------
'''
# Assign Functions to Threads
t1 = threading.Thread(target=rng_record)
t2 = threading.Thread(target=rng_control)

# Define Start Time
start_time = time.time()

# Start Data Generation
t2.start()

'''
Plotting Loop
-------------
'''

# Wait until t1 is running
while not t1.is_alive():
    time.sleep(1)
time.sleep(1)


# Find Instrument Start Time
t_start = rng_data[1, -1]/1e3  # seconds

while not exitFlag:
    # Update Line 1
    plt.gca().lines[0].set_xdata(rng_data[1:, -1]/1e3 - t_start)
    plt.gca().lines[0].set_ydata(rng_data[1:, 0]/1e3)
    # Update Line 2
    plt.gca().lines[1].set_xdata(rng_data[1:, -1]/1e3 - t_start)
    plt.gca().lines[1].set_ydata(rng_data[1:, 1]/1e3)
    # Rescale x-axis (time)
    t_end = rng_data[-1, -1]/1e3 - t_start
    if t_end < view_t:
        plt.xlim(0, t_end)
    else:
        plt.xlim(t_end - view_t, t_end)
    # Rescale y-axis
    sig_min = np.amin(rng_data[:, :2]/1e3)
    if sig_min > 0:
        sig_min = 0
    sig_max = np.amax(rng_data[:, :2]/1e3)
    if sig_max < 10:
        sig_max = 10
    plt.ylim(sig_min, sig_max + sig_max/10)
    # plt.gca().relim()
    # plt.gca().autoscale_view()
    fig.canvas.flush_events()
    plt.pause(1e-6)
    time.sleep(1)

# Wait until t1 is finished
t1.join()

'''
Finally, save data and figures
'''
# Close Serial Port
rng.close()
# Close figure
plt.close(fig)

# Delete first row (place holder)
rng_data = rng_data[1:, ]

# Save entire data set as CSV-file
file_datetime = datetime.datetime.today()
csv_file_name = file_datetime.strftime('output/%y%m%d_%H%M_%S_rng_data.csv')
np.savetxt(fname=csv_file_name, X=rng_data, delimiter=',', header=','.join(['A_Wl1', 'A_Wl2', '<empty>', 'DeviceTemperature', 'TimeStamp']), comments='')

# Save log file
log_file_name = file_datetime.strftime('output/%y%m%d_%H%M_%S_rng_log.txt')
with open(log_file_name, 'w') as f:
    for item in rng_log:
        f.write("%s\n" % item)

# Make summary figure including entire data set
fig_1 = plt.figure(figsize=[14, 7])
line1, = plt.plot(rng_data[:, -1]/1e3 - t_start, rng_data[:, 0]/1e3, '-r', linewidth=0.5)
line2, = plt.plot(rng_data[:, -1]/1e3 - t_start, rng_data[:, 1]/1e3, '-b', linewidth=0.5)
plt.draw()

# Figure labels
plt.suptitle('Runge mikron 31: Absorbance')
plt.xlabel('Time (s)')
plt.ylabel('Absorbance (mAU)')
plt.legend((line1, line2), (Wl1, Wl2), loc=2, ncol=2, frameon=False)

# Save figure to pdf
pdf_file_name = file_datetime.strftime('figures/%y%m%d_%H%M_%S_rng_data.pdf')
plt.savefig(fname=pdf_file_name)

# Block Figure (close manually)
plt.show(block=True)
