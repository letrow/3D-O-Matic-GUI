#!/usr/bin/python3
# -*- coding: utf-8 -*-
"""
Date:     2022-08-27
Author:   Hans Schulz
Description:
    3D-Gui is a simple 3D-printer host program for
    Marlin-based printers via a serial port.

"""
from ttkthemes import ThemedTk, themed_style
import time

# local imports:
import data, pospanel, temppanel, jogpanel, \
       dialogpanel, textpanel, transport as tr

def die():
   time.sleep(0.1)
   gui.destroy()          
   data.stop_decoder()

# set global system state defaults:
data.port = "/dev/ttyACM0"
data.baud = 250000
data.connected = False
data.gcodeFile = None
data.fileSize = 0
data.curline = 0
data.linenum = 0
data.ready = False
data.homed = set()
data.selectedAxis = None
t0 = time.time()

''' 
The start() and run() event handlers form a simple state machine, depending
on the status of the communcation link with the printer, as indicated by
ready. If start() is active the program sits in a waiting loop until the
link is up. In that case the program switches to the run() handler and
operational updating of the gui is executed.
'''
    
def start():
    global t0
    if not data.ready:  # postpone transmission until printer ready
        gui.after(500, start)  # loop here until printer ready
    else:
#        data.xmtQ.put('M110 N'+str(data.linenum))   # init line number
        data.xmtQ.put('M154 S5')   # start auto position report
        data.xmtQ.put('M155 S5')   # start auto temperatures report
        data.xmtQ.put('M302 P1')   # enable cold extrusion
        time.sleep(0.1)    # allow linenum to get updated by transceiver
        t0 = time.time()      # get starttime for run()
        gui.after(10, run)     # start main event handler
    
def run():   
    global t0
    if time.time() - t0 > 2.0:  # update the gui once per x seconds 
        t0 = time.time()
        # update positions panel:
        pos.update(data.pos)
        # update temperatures:
        e0tmp.setPV(data.tmp['T0:']['PV'])
        e0tmp.setSP(data.tmp['T0:']['SP'])
        e1tmp.setPV(data.tmp['T1:']['PV'])
        e1tmp.setSP(data.tmp['T1:']['SP'])
        bedtmp.setPV(data.tmp['B:']['PV'])
        bedtmp.setSP(data.tmp['B:']['SP'])
        if transport.printing:
            # show progress bar
            status.txt.config(state = 'normal')
            status.txt.insert ('insert linestart', data.progress(transport.linenum, 
                                                                  data.filesize, 
                                                                  30))
            status.txt.delete('insert linestart', 'end lineend')
            status.txt.update()
            status.txt.config(state = 'disabled')
            # disable jogging:
            jog.disable()
            pos.disable()
        else:
            jog.enable()
            pos.enable()
            dlgs.stopPrint()
    # figure out what to do next:
    if not data.ready:
        gui.after(10, start)    # restart comms when needed
    else:
        gui.after(1000, run)

# create root level:
gui = ThemedTk(theme="black")    # equilux is nice too     
gui.title('3D-O-Matic Marlinterface')
gui.configure(bg='black')
gui.style = themed_style.ThemedStyle()
gui.protocol('WM_DELETE_WINDOW', die)

# add components to gui:
status = textpanel.Textpanel(gui, ' System Status', h=7, w=40, sb=0)
transport = tr.Transport(status=status)
info = textpanel.Textpanel(gui, ' Info from Printer', h=15, w=90)
dlgs = dialogpanel.Dialogpanel(gui, transport, info, status)
jog = jogpanel.Jogpanel(gui, status)
pos =  pospanel.Pospanel(gui)
e0tmp = temppanel.Temppanel(gui,'Extruder 0', 'T0', 'M104')
e1tmp = temppanel.Temppanel(gui,'Extruder 1', 'T1', 'M104')
e0tmp.setPV(180)
bedtmp = temppanel.Temppanel(gui,'Heated Bed', '', 'M140')
bedtmp.setScale(100)
mdi = textpanel.Textpanel(gui, ' MDI', h=1, w=30, sb=0)
data.init(info, status)

# place panels on the screen:
dlgs.grid(row=0, column=0, columnspan=3, padx=5, pady=1, sticky='W')  
status.grid(row=1, column=0, columnspan=1, rowspan=2, padx=5, pady=1, sticky='SEW')
pos.grid(row=1, column=1, rowspan=2, padx=5, pady=1, sticky='SEW')  
jog.grid(row=3, column=1, rowspan=2, padx=5, pady=1, sticky='SEW')
e0tmp.grid(row=1, column=2, padx=5, pady=1, sticky='SE')  
e1tmp.grid(row=2, column=2, padx=5, pady=1, sticky='SE')  
bedtmp.grid(row=3, column=2, padx=5, pady=1, sticky='SE')  
mdi.grid(row=3, column=0, columnspan=1, padx=5, pady=5, sticky='SW')
info.grid(row=6, column=0, columnspan=3, padx=5, pady=5, sticky='EW')

start()
gui.mainloop()
