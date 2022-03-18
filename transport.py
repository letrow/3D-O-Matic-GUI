#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Mon Mar 14 10:48:22 2022

@author: hschulz
"""

import threading
import re
import time

from serial import Serial, SerialException, PARITY_NONE
from model import xmtQ, rcvQ
import model

port = 0
baud = 0
status = None   # gui status panel
printer = None  # our printer port
logfile = None  # debug...

# init free bytes count (Marlin's MAX_COMMAND_SIZE as a reasonable basis)
free = [96,]
kill = False    # controls the transceiver thread
resending = 0
nxtcmd = ''
rescmd = ''
resendQ = []
mode = 0


#------------------------------------------------------------------------------    
# helper routines
#------------------------------------------------------------------------------    
def crc8(data):
    cs = 0
    for i in range(len(data)):
        cs ^= ord(data[i])
    return cs & 0xff

def _addenv(cmd):
    ''' Add line number and checksum to cmd if not already present. '''
    if not re.findall('^N\d*', cmd): # no envelope yet?
        cmd = 'N'+ str(model.linenum) + ' ' + cmd
        cmd = cmd + '*' + str(crc8(cmd))
        model.linenum += 1
    return cmd
    
def _xmtOk(cmd):
    ''' Helper function for transceiver:
        Try to transmit cmd to the printer and update queues.
        Return True if success, False otherwise. '''
    global free, resendQ, printer
    try:
        # check for space in Marlin's buffer:
        cmdsize = len(cmd) + 1 # plus newline
        if sum(free) < cmdsize:
            return False
        else:
            free.append(-cmdsize)  # subtract # of bytes from free
            resendQ.append(cmd) # save in history
#            logfile.write('>> ' + cmd + '\n')
            printer.write((cmd+'\n').upper().encode())
            return True
    except Exception as e:
        print(e)
        
#------------------------------------------------------------------------------    
# transceiver thread
#------------------------------------------------------------------------------    
def transceiver():
    ''' Thread handles all communication with the printer. '''
    global nxtmd, rescmd, mode, logfile, resending, kill
    status.show('transceiver thread started\n')
    waitingOk = 0
    model.linenum = 1
#    logfile = open('logfile.log', 'w')
    while not kill:
        try:
#            logfile.flush()
            if printer.in_waiting:  # parse data from printer
                # Resend:
                data = printer.readline().decode('ascii') 
#                logfile.write('<<' + data.rstrip() + '\n')
                if re.findall('^Resend', data) and \
                                model.printing and \
                                not resending:
                    if waitingOk < -1:    # ignore resends when still resending
                        resending = len(resendQ)   # amount of cmds to recirculate
                        waitingOk = resending      # amount of Ok's to consume
                        status.show('resending from line N{}\n'. \
                                    format(str(*re.findall('^N(\d*)', resendQ[0]))))
                        rescmd = ''
                        mode = 2    # circulate
                    elif waitingOk == -1: # Retried cmd still bad!
                        # persistent error after resend:
                        model.printing = False
                        mode = 0
#                        logfile.write('\nabort\n')
                        status.show('\npersistent error; printing aborted\n')
                # Ok:        
                elif re.findall('^ok', data):
                    waitingOk = max (-2, waitingOk-1)
                    if mode != 2:   # skip when resending
                        free.pop(1)     # remove bytecount from free
                        resendQ.pop(0)   # drop cmd from history, non blocking

                # Echo, Error or status messages:
                if len(data) > 4: # even 'ok' may be followed by temp report!
                    rcvQ.put(data)
                
            # execute selected transmit mode function:
            modetab[mode]()

        except IndexError as e:
#            logfile.write(str(e) + '\n')
#            logfile.flush()
            pass
        except Exception as e:
            print(e)
            kill = True
    # get here when killed:
    print('transceiver killed')
    if model.printing:
        model.gcodeFile.close()
#    logfile.close()


#------------------------------------------------------------------------------    
# transmitter mode functions
#------------------------------------------------------------------------------    
def fromGui():
    global nxtcmd, mode
    if not nxtcmd:   # no previous cmd pending?
        if not model.xmtQ.empty(): # get command from xmt queue - if any
            nxtcmd = xmtQ.get()
        # remove empty lines and comments:
        nxtcmd = re.sub( ';.*$', '', nxtcmd).rstrip()
    if nxtcmd:
        nxtcmd = _addenv(nxtcmd)    # add envelope (if needed)
        if _xmtOk(nxtcmd):
            nxtcmd = ''
    if model.printing:
        mode = 1
    
def fromFile():
    global nxtcmd, mode
    if not nxtcmd:   # no previous cmd pending?
        nxtcmd = model.gcodeFile.readline() # get from g-code file
        model.curline += 1
        if not model.printing: # aborted?
            mode = 0
            return
        if nxtcmd == '': # EOF
            model.printing = False
            mode = 3    # finalize printing before returning to idle
#            logfile.write('EOF\n')
            return
        # remove empty lines and comments:
        nxtcmd = re.sub( ';.*$', '', nxtcmd).rstrip()
    if nxtcmd:
        nxtcmd = _addenv(nxtcmd)    # add envelope (if any)
        if _xmtOk(nxtcmd):    # add envelope (if any)):
            nxtcmd = ''
            
def circulate():
    global rescmd, resending, mode
    if not rescmd:  # no previous attempt pending?
        rescmd = resendQ.pop(0) # get command from history
        free.pop(1)             # circulate bytecount
#===================== these lines are for testing only========================
#    if re.findall('^N12', rescmd): # fix crc error
#        rescmd = re.sub('\*108', '*107', rescmd)
#==============================================================================
    if _xmtOk(rescmd):
        resending = max(0, resending-1)
        rescmd = ''
        if not resending:
            mode = 1    # back to regular printing
        
def finalize():
    global mode
    if len(free) == 1:   # wait for all ok's to get processed
        mode = 0    # back to idle
        status.show('\nPrinting Completed\n')

# transmitter functions per mode:
modetab = [
    fromGui,   # mode 0: normal interactive operation when not printing
    fromFile,  # mode 1: printing: obtain commands from g-code file
    circulate, # mode 2: printing with resend request in progress
    finalize]  # mode 3: EOF reached, finalize printing   

#------------------------------------------------------------------------------    
# transceiver thread initialization
#------------------------------------------------------------------------------    
def init(p, b, output1, output2):
    ''' open serial port, start receiver and transceiver thread.'''
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
        printer.setDTR(0)   # hardware reset for target machine
        time.sleep(1)
        printer.setDTR(1)
    except SerialException as e:
        print(e)
        return -1   # error!

    # create thread for non-blocking input and start it:
    xmtr = threading.Thread(target = transceiver)
    xmtr.start()
    return 0
