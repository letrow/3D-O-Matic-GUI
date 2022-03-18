#!/usr/bin/env python3
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

#------------------------------------------------------------------------------    
# shared data
#------------------------------------------------------------------------------    

xmtQ = queue.Queue()    # data from gui to printer
rcvQ = queue.Queue(200) # data from printer to gui (truncated)

gcodeFile = None    # file object being printed
filesize = 0        # number of lines in gcodeFile
curline = 0         # current line being printed

# machine state variables:
selectedAxis = None
selectedExtruder = 0
powerIsOn = True
homed = set()
connected = False
printing = False
linenum = 1

pos = [0., 0., 0., 0., None, None, None]  # X, Y, Z, E reported positions
tmp = {
      'T0:': {'PV': -1, 'SP': -1},
      'T1:': {'PV': -1, 'SP': -1},
      'B:':  {'PV': -1, 'SP': -1}}

port = '/dev/ttyACM0'
baud = 250000
ready = False   # printer is ready to receive commands
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
# decoder stuff
#------------------------------------------------------------------------------    

# text output panels:
info = None
status = None
kill = False

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
    global xmtQ, rcvQ, pos, tmp
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
#  core system initialization
#------------------------------------------------------------------------------    

def init(output1, output2):
    global info, status
    info, status = output1, output2
    xmtQ._init(10000)   # set maxsize for queues
    rcvQ._init(10000)   # (queue full exception means something is really wrong)
    dec = threading.Thread(target = decoder)
    try:
        dec.start()
        return 0
    except:
        return -1
