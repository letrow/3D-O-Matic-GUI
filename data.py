#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Sat Aug 27 12:49:51 2022

@author: hschulz
This module contains all gobal vars for the 3D-Gui program
"""
import queue, re, threading

# global data:
port = None             # serial port name
baud = None             # serial baud rate
connected = None        # true if link to printer established
gcodeFile = None        # handle to open gcode file
fileSize = 0            # numlines in gcode
ready = False           # printer reported ready
homed = set()           # axes that have been homed
selectedAxis = None     # current axis to jog

#------------------------------------------------------------------------------    
# decoder stuff
#------------------------------------------------------------------------------    

decoder_thread = None   # the decoder if running
kill = False            # kills decoder thread if True

# queues for asynchronous communication with transport:
xmtQ = None    # data from gui to printer
rcvQ = None    # data from printer to gui

# text output panels:
info = None
status = None

# gui data:
pos = [0., 0., 0., 0., None, None, None]  # X, Y, Z, E reported positions
tmp = {
      'T0:': {'PV': -1, 'SP': -1},
      'T1:': {'PV': -1, 'SP': -1},
      'B:':  {'PV': -1, 'SP': -1}}

def setPositions(m):
    ''' Update positions data for reported axes. '''
    global pos
    for i, n in enumerate(m): # all but extruder pos
        pos[i] = float(n)

def setTemperatures(m):
    ''' Update all reprted temperature data. '''
    global tmp
    try:
        for grp in m[1::]:  # first group is redundant: skip
            tmp[grp[0]]['PV'] = float(grp[1])
            tmp[grp[0]]['SP'] = float(grp[2])
    except Exception as e:
        print(e)

def setReadyFlag(m):
    global ready
    status.show('Printer ready\n')
    ready = True

def setExtruder(m):
    ''' Update extruder selection. '''
    global selectedExtruder
    try:
        selectedExtruder = int(m[0])
    except Exception as e:
        print(e)
        
def waitExtruder(m):
    ''' Update temperature value for specified extruder. '''
    tmp['T'+tuple(*m)[1]+':']['PV'] = float(tuple(*m)[0])
    
def waitBed(m):
    ''' Update temperature value for heated bed.'''
    tmp['B:']['PV'] = float(tuple(*m)[2])

# decoder table and parser regex's:
#m105report_exp = re.compile("[TB]\d*:([-+]?\d*\.?\d*)(?: ?\/)?([-+]?\d*\.?\d*)")
m105report_exp = re.compile('([BT][01]?:)([+-]?\d*?\.\d*?)\s*?\/(\d*\.\d*)')
m114report_exp = re.compile("[XYZE]:(-?\d+\.\d+)")
ready_exp = re.compile("(echo:\s*M217).*") # last line in welcome message
prusa_ready_exp = re.compile("(echo:\s*SD\sinit).*") # same for prusa i3
actExt_exp = re.compile("Active\s+Extruder:\s*([01])")
# following decodes msg after M109 or M190
ext_warmup_exp = re.compile('^T:(\d*\.\d*)\s*E:(\d*)\s*(W:[?0-9]{1,2}$)$')
bed_warmup_exp = re.compile('^T:(\d*\.\d*)\s*E:(\d*)\s*B:(\d*\.\d*)$')

# when the regex in this table matches, the associated function is called
decTable = [(m114report_exp, setPositions),
            (m105report_exp, setTemperatures),
            (ready_exp, setReadyFlag),
            (prusa_ready_exp, setReadyFlag),
            (actExt_exp, setExtruder),
            (ext_warmup_exp, waitExtruder),
            (bed_warmup_exp, waitBed)]

def decoder():
    ''' thread to monitor rcvQ and decode incoming data from printer. '''
    global xmtQ, rcvQ, pos, tmp, kill, info, status
    status.show('decoder thread started\n')
    while not kill:
        if not rcvQ.empty():
            try:
                data = rcvQ.get()
                # decode message:
                for regex, function in decTable:
                    match = re.findall(regex, data)
                    if match:   # execute associated decoder function
                        function(match)
                        break
                else:   # no match:
                    info.show(data) # data is informational so show it                
            except queue.Empty:
                pass
    # get here when killed:
    print('decoder killed')

#------------------------------------------------------------------------------    
# helper functions
#------------------------------------------------------------------------------    

def progress(done, total, width):
    '''Return progress string of width chars wide. '''
    if total:
        s = '['
        for i in range(width):
            completed = width * done/total
            s += '#'if i <= completed else '.'
        s += '] {:3.1f}%\n'.format(100 * done/total)
        return s
    else:
        return '\n'
    
#------------------------------------------------------------------------------    
#  decoder initialization
#------------------------------------------------------------------------------    

def init(output1, output2):
    global info, status, decoder_thread, kill, xmtQ, rcvQ
    info, status = output1, output2
    xmtQ = queue.Queue()
    rcvQ = queue.Queue()
    kill = False
    decoder_thread = threading.Thread(target = decoder)
    try:
        decoder_thread.start()
        return 0
    except:
        return -1
        
def stop_decoder():
    global decoder_thread, kill
    if decoder_thread:
        kill = True
        decoder_thread.join()
        decoder_thread = None

