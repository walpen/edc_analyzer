"""
Communicate with Cadent 3 Syringe Pump via RS-232
"""

# Import modules
import pandas as pd
import csv
import serial
import datetime
import time

"""
Start user input
"""

# Name of serial port
# To find serial port address, open terminal, enter "ls /dev/{cu,tty}.*"
# port_name: str = '/dev/tty.UC-232AC'
port_name: str = '/dev/tty.usbserial'

# Path to list of commands (CSV-file)
input_file_name = 'input/c3_cmd_lst.csv'

# Command list repetitions: number of repetitions that the command list is sent to device
cmd_lst_rep = 1

# List of commands to be sent
# cmd_lst: list = ['~V', 'A2000R', 5, 'o2R', 'A8000R', 'o4R', 'A3000R', 'o3R', '~V']


"""
End user input
"""

# Start Time
start_time = time.time()

# Script start message
strt_msg: str = "Cadent-3 Commuincation via RS-232"
print('\n'.join(['', strt_msg, '-' * len(strt_msg)]))

#
# Read list of commands
#
df = pd.read_csv(input_file_name)
# Initialize command list
cmd_lst: list = list()
# Iterate over rows
for row in df.itertuples():
    # Read Block
    tmp_block = getattr(row, 'Block')
    # Read Step
    tmp_step = getattr(row, 'Step')
    tmp_block_step = [tmp_block, tmp_step]
    # Append to list of commands
    cmd_lst.append(tmp_block_step)
    # Read command
    tmp_command = getattr(row, 'Command')
    # Append to list of commands
    cmd_lst.append(tmp_command)
    # Read sleep time
    tmp_sleep = getattr(row, 'Sleep')
    # If sleep time is positive, append
    if tmp_sleep > 0:
        cmd_lst.append(tmp_sleep)
# Repetitions
cmd_lst = cmd_lst * cmd_lst_rep
# Print list of commands
print('\nList of commands: ')
print(cmd_lst)
print('\n')

# Commands that need time to execute
cmd_wait: tuple = (
    # Syringe Commands
    '/1A',  # Move syringe to absolute position n.
    '/1D',  # Dispense n steps from the current position.
    '/1P',  # Aspirate n steps from the current position.
    # Valve Commands
    '/1o',  # Move valve to position X with '/1oX'
    # Syringe Variables
    '/1V'  # Set Syringe Speed
)

#
# Create log file (or append)
#
# Define name of the log file
log_file_name: str = ''.join(['output/', str(datetime.date.today()), '_log_cadent.csv'])
# Try to read log file
try:
    # try reading file
    log_file = open(log_file_name, 'r')
    log_file.close()
except FileNotFoundError:
    # If file does not exist yet, create it
    log_file = open(log_file_name, 'w', newline='')
    # Create writer object
    logger = csv.writer(log_file)
    # Header of log file
    log_file_header: list = ['Datetime', 'Command', 'Response']
    # Write header and port status
    logger.writerows([log_file_header])
    log_file.close()

# Open port
try:
    cdt = serial.Serial(port=port_name, timeout=1)
except serial.serialutil.SerialException:
    cdt = serial.Serial()

# Check status of port
if cdt.is_open:
    port_status: str = "Port opened"
else:
    port_status: str = "Failed to open port"
# Print port status
print(''.join(["Status: ", port_status]))
# Check which port was really used
print(''.join(["Serial Port Address: ", str(cdt.name), '\n']))
# Save time stamp
time_stamp = datetime.datetime.now()
# Write port status to log file
log_port_status: list = [str(time_stamp), '', port_status]
with open(log_file_name, 'a') as log_file:
    logger = csv.writer(log_file)
    logger.writerows([log_port_status])


#
# Define Functions
#
# Define Listening Function
def rec_rsp(cmd_snt: str = ''):
    # Read for response from device
    rsp_full: bytes = cdt.readline()
    # rsp_full: bytes = cdt.read_until(terminator='\x03\r\n\xff')
    # Remove ending characters
    rsp_no_space = rsp_full.replace(b'\xff', b'')
    rsp = rsp_no_space.replace(b'\x03\r\n', b'')
    # Print received command
    print(''.join(['> ', rsp.decode()]))
    # Add time stamp to command
    rsp_log: list = [str(datetime.datetime.now()), cmd_snt, rsp.decode()]
    with open(log_file_name, 'a') as log_file:
        logger = csv.writer(log_file)
        logger.writerows([rsp_log])
    # Wait until device is ready again
    c3wait()


# Define Command and Response Function for Cadent-3
def send_cmd(cmd: str = '?'):
    # Add device address '/1' and ending character '\r'
    cmd_full: str = ''.join(['/1', cmd, '\r'])
    # If port is open, send command
    if cdt.is_open:
        # Print full command to be sent
        print(''.join(['\n', cmd]))
        # Send full command to device
        cdt.write(bytearray(cmd_full, "ascii"))
        # Listen for response
        rec_rsp(cmd_snt=cmd_full)
    else:
        print('Did not send command (%s), port closed' % cmd)


def c3wait():
    # Release when device ready again
    while True:
        cdt.write(bytearray('/1?\r', "ascii"))
        rsp_status: bytes = cdt.read_until(b'\x03\r\n\xff')
        if rsp_status.startswith(b'/0`'):
            rsp_status_no_space = rsp_status.replace(b'\x03\r\n\xff', b'')
            print(''.join(['\r> ', rsp_status_no_space.decode()]))
            break
        elif rsp_status.startswith(b'/0i'):
            rsp_status_no_space = rsp_status.replace(b'\x03\r\n\xff', b'')
            raise Exception(''.join(['> Device Error ', rsp_status_no_space.decode()]))
        rsp_status_tmp = rsp_status.replace(b'\x03\r\n', b'')
        rsp_status_no_space = rsp_status_tmp.replace(b'\xff', b'')
        print(''.join(['\r> Device busy: ', rsp_status_no_space.decode()]), end='')
        time.sleep(1)


#
# Send Commands
#
for cmd_i in cmd_lst:
    if isinstance(cmd_i, str):
        send_cmd(cmd=cmd_i)
    elif isinstance(cmd_i, int):
        time_stamp = datetime.datetime.now()
        time_start = time_stamp.strftime('%H:%M:%S')
        time_stamp_end = time_stamp + datetime.timedelta(seconds=cmd_i)
        time_end = time_stamp_end.strftime('%H:%M:%S')
        print(
            ''.join(['> Delay: ', str(cmd_i), ' seconds\n>> Start: ', str(time_start), '\n>> End:   ', str(time_end)]))
        time.sleep(cmd_i)
    elif isinstance(cmd_i, list):
        print(''.join(['\nBlock: ', cmd_i[0], '\nStep: ', cmd_i[1]]))

#
# Close Port
#
if cdt.is_open:
    print('\nClosing port ...')
    # Close serial port
    cdt.close()
    # Save time stamp
    time_stamp = datetime.datetime.now()
    # Check port status
    if cdt.is_open:
        port_status: str = "Failed to close port"
    else:
        port_status: str = "Port closed"
    # Print port status
    print("Status: " + port_status + "\n")
    # Write port status to log file
    log_port_status: list = [str(time_stamp), '', port_status]
    with open(log_file_name, 'a') as log_file:
        logger = csv.writer(log_file)
        logger.writerows([log_port_status])

# Report time
end_time = time.time()
duration = round((end_time - start_time) / 60, 2)
print(''.join(['\nDuration: ', str(duration), ' min\n']))
