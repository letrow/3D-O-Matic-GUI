#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Mon Feb 21 17:28:41 2022

@author: hschulz
"""

from ttkthemes import ThemedTk, themed_style
import time, re
import pospanel, temppanel, jogpanel, transport, \
       model, dialogpanel, textpanel
''' 
The start() and run() event handlers form a simple state machine, depending
on the status of the communcation link with the printer, as indicated by
ready. If start() is active the program sits in a waiting loop until the
link is up. In that case the program switches to the run() handler and
operational updating of the gui is executed.
'''

t0 = 0
def start():
    global t0
    if not model.ready:  # postpone transmission until printer ready
#        print('.', end='') # waiting for printer
        gui.after(500, start)  # stay here until printer ready
    else:
#        model.xmtQ.put('M154 S3')   # start auto position report
#        time.sleep(2)
#        model.xmtQ.put('M155 S3')   # start auto temperatures report
        t0 = time.time()            # get starttime for run()
        gui.after(10, run)          # start main event handler
        
def run():   
    global t0
    if time.time() - t0 > 2.0:  # update the gui once per x seconds
        t0 = time.time()
        # update positions panel:
        model.xmtQ.put('M114')
        pos.update(model.pos)
        # update temperatures:
        model.xmtQ.put('M105')  # ensure we have a temp report next time
        e0tmp.setPV(model.tmp['T0:']['PV'])
        e0tmp.setSP(model.tmp['T0:']['SP'])
        e1tmp.setPV(model.tmp['T1:']['PV'])
        e1tmp.setSP(model.tmp['T1:']['SP'])
        bedtmp.setPV(model.tmp['B:']['PV'])
        bedtmp.setSP(model.tmp['B:']['SP'])
            
    # update the dialogs:
    dlgs.update()
    # figure out what to do next:
    if not model.ready:
        gui.after(10, start)    # restart comms when needed
    else:
        gui.after(2, run)
    
# creating root
#gui = tk.Tk()
gui = ThemedTk(theme="equilux")    # equilux is nice too     
gui.title('3D-O-Matic Marlinterface')
gui.configure(bg='black')
#gui.style = ttkthemes.themed_style.ThemedStyle()
gui.style = themed_style.ThemedStyle()

try:
    # build the gui:
    status = textpanel.Textpanel(gui, ' System Status', h=7, w=40, sb=0)
    info = textpanel.Textpanel(gui, ' Info from Printer', h=15, w=90)
    dlgs = dialogpanel.Dialogpanel(gui, info, status)
    jog = jogpanel.Jogpanel(gui)
    pos =  pospanel.Pospanel(gui)
    e0tmp = temppanel.Temppanel(gui,'Extruder 0', 'T0', 'M104')
    e1tmp = temppanel.Temppanel(gui,'Extruder 1', 'T1', 'M104')
    bedtmp = temppanel.Temppanel(gui,'Heated Bed', '', 'M140')
    bedtmp.setScale(100)
    mdi = textpanel.Textpanel(gui, ' MDI', h=1, w=30, sb=0)
    
    dlgs.grid(row=0, column=0, columnspan=3, padx=5, pady=1, sticky='W')  
    status.grid(row=1, column=0, columnspan=1, rowspan=2, padx=5, pady=1, sticky='SEW')
    pos.grid(row=1, column=1, rowspan=2, padx=5, pady=1, sticky='SEW')  
    jog.grid(row=3, column=1, rowspan=2, padx=5, pady=1, sticky='SEW')
    e0tmp.grid(row=1, column=2, padx=5, pady=1, sticky='SE')  
    e1tmp.grid(row=2, column=2, padx=5, pady=1, sticky='SE')  
    bedtmp.grid(row=3, column=2, padx=5, pady=1, sticky='SE')  
    mdi.grid(row=3, column=0, columnspan=1, padx=5, pady=5, sticky='SW')
    info.grid(row=6, column=0, columnspan=3, padx=5, pady=5, sticky='EW')

    # start decoder and initialize data:
    if model.init(info, status) < 0:    # start decoder thread
        print('*** Decoder initialization failed ***')
        exit()
        
    # start the program:
    start()
    gui.mainloop()
    
except KeyboardInterrupt:
    print('bye...')
    
finally:
    transport.kill=True
    model.kill = True
