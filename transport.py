#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Fri Feb 25 09:05:14 2022

@author: hschulz

<TODO>
- timeout on wait for ack
"""
import threading
import time
import re
import os

from serial import Serial, SerialException, PARITY_ODD, PARITY_NONE
from model import xmtQ, rcvQ
import model

port = 0
baud = 0
status = None
printer = None
# init free bytes count (Marlin's MAX_COMMAND_SIZE x BUFSIZE ??)
free = [96,]
kill = False    # keeps the transceiver thread alive
#state = 0


def receiver():
    ''' Thread for receiving data from the printer. '''
    global free
    status.show('receiver thread started\n')
    while not kill:
        try:
            if printer.in_waiting:  # there is data received from printer
                line = printer.readline()
                data = line.decode('ascii') 
                if re.findall('^ok', data):
                    free.pop(1) # release bytecount from free
                    print('...ok; free:', free)
                    if len(data) < 4: # 'ok' may be followed by temp report!
                        continue
                elif re.findall('^echo:\s*cold', data):
                    continue    # ignore cold extrusion messages
                rcvQ.put(data)
        except Exception as e:
            print(e)
    # get here when killed:
    printer.close()
    print('receiver killed')


def transmitter():
    ''' Thread to send data to the printer. '''
    status.show('transmitter thread started\n')
    while not kill:
        try:
            cmd = ''
            if not model.xmtQ.empty(): # get command from xmt queue - if any
                cmd = xmtQ.get()
            elif model.printing: # we're printing: get command from gcode file:
                cmd = model.gcodeFile.readline()
                if cmd == '': # EOF
                    model.printing = False
                    status.show('Printing Completed\n')
                    continue
            else:
                continue # no data AND not printing: do nothing
            # remove empty lines and comments:
            cmd = re.sub( ';.*$', '', cmd).rstrip()
            if cmd: # anything left?
                # wait until space in Marlin's buffer:
                cmdsize = len(cmd) + 1 # plus newline
                while sum(free) < cmdsize:
                    pass
                free.append(-cmdsize)  # subtract # of bytes from free
                print(cmd)
                printer.write((cmd+'\n').upper().encode())
        except Exception as e:
            print(e)
    # get here when killed:
    if model.printing:
        model.gcodeFile.close()
    print('transmitter killed')


def init(p, b, output1, output2):
    ''' open serial port, start receiver and transmitter threads.
    '''
    global port, baud, printer, kill, status, info
    # set local vars:
    port, baud, info, status = p, b, output1, output2

    # open port and reset printer:
    kill = False    
    try:
        printer = Serial(port = port,
                      baudrate = baud,
                      timeout = 0.25,
                      parity = PARITY_NONE)
        if not printer.isOpen():
            printer.open()
        printer.flush()
        printer.setDTR(1)
        printer.setDTR(0)

    except SerialException as e:
        print("Could not connect to {} at baudrate {}:".format(port, baud))
        return -1   # error!

    # create thread for non-blocking input and start it:
    xmtr = threading.Thread(target = transmitter)
    rcvr = threading.Thread(target = receiver)
    rcvr.start()
    xmtr.start()
    return 0
    
    
