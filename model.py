#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Tue Feb 22 18:38:38 2022

@author: hschulz
This unit provides all global variables for the 3D-GUI program.
It serves as an interface / data exchange between the various modules.
"""
import queue
import threading
import re
import time

xmtQ = queue.Queue()    # data from gui to printer
rcvQ = queue.Queue(200) # data from printer to gui (truncated)

gcodeFile = None

# text output panels:
info = None
status = None
kill = False

# machine state variables:
selectedAxis = None
selectedExtruder = 0
powerIsOn = True
homed = set()
connected = False
printing = False

pos = [0., 0., 0., 0., None, None, None]  # X, Y, Z, E reported positions
tmp = [1.2, 3.4,              # E0 process value, E0 setpoint
       0.5, 0.6,              # E0 pv, E1 sp,
       0.7, 0.8]              # bed pv, bed sp

tmp = {
      'T0:': {'PV': -1, 'SP': -1},
      'T1:': {'PV': -1, 'SP': -1},
      'B:':  {'PV': -1, 'SP': -1}}

port = '/dev/ttyACM0'
baud = 250000
ready = False   # printer is ready to receive commands

def setPositions(m):
    ''' Store data. '''
    global pos
    for i, n in enumerate(m): # all but extruder pos
        pos[i] = float(n)

def setTemperatures(m):
    global tmp
    try:
        for grp in m[1::]:  # first group is redundant: skip
            tmp[grp[0]]['PV'] = float(grp[1])
            tmp[grp[0]]['SP'] = float(grp[2])
    except Exception as e:
        print(e)

def setReadyFlag(m):
    global ready
    ready = True
    status.show('Printer ready\n')

def setExtruder(m):
    global selectedExtruder
    try:
        selectedExtruder = int(m[0])
    except Exception as e:
        print(e)

# decoder table and parser regex's:
#m105report_exp = re.compile("[TB]\d*:([-+]?\d*\.?\d*)(?: ?\/)?([-+]?\d*\.?\d*)")
m105report_exp = re.compile('([BT][01]?:)([+-]?\d*?\.\d*?)\s*?\/(\d*\.\d*)')
m114report_exp = re.compile("[XYZE]:(-?\d+\.\d+)")
ready_exp = re.compile("(echo:\s*M217).*") # last line in welcome message
prusa_ready_exp = re.compile("(echo:\s*SD\sinit).*") # same for prusa i3
actExt_exp = re.compile("Active\s+Extruder:\s*([01])")

decTable = [(m114report_exp, setPositions),
            (m105report_exp, setTemperatures),
            (ready_exp, setReadyFlag),
            (prusa_ready_exp, setReadyFlag),
            (actExt_exp, setExtruder)]

def decoder():
    ''' thread to monitor rcvQ and decode incoming data from printer. '''
    global xmtQ, rcvQ, pos, tmp
    while not kill:
        if not rcvQ.empty():
            try:
                data = rcvQ.get()
                # decode message:
                for regex, function in decTable:
                    match = re.findall(regex, data)
                    if match:   # execute associated decoder function
                        function(match) # call vectored function
                        break
                else:   # no match:
                    info.show(data) # data is informational so show it                
            except queue.Empty:
                pass
            time.sleep(0.2)
    # get here when killed:
    print('decoder killed')

def init(output1, output2):
    global info, status
    info, status = output1, output2
    xmtQ._init(10000)    # set maxsize for queues
    rcvQ._init(10000)
    dec = threading.Thread(target = decoder)
    try:
        dec.start()
        status.show('decoder thread started\n')
        return 0
    except:
        return -1
