#!/usr/bin/env python3
"""
Created on Mon Feb 21 17:28:41 2022

@author: hschulz
"""

from ttkthemes import ThemedTk, themed_style
import time
import pospanel, temppanel, jogpanel, transport, \
       model, dialogpanel, textpanel
''' 
The start() and run() event handlers form a simple state machine, depending
on the status of the communcation link with the printer, as indicated by
ready. If start() is active the program sits in a waiting loop until the
link is up. In that case the program switches to the run() handler and
operational updating of the gui is executed.
'''

def start():
    global t0
    if not model.ready:  # postpone transmission until printer ready
        gui.after(500, start)  # loop here until printer ready
    else:
        model.xmtQ.put('M110 N'+str(model.linenum))   # init line number
        model.xmtQ.put('M154 S3')   # start auto position report
        model.xmtQ.put('M155 S3')   # start auto temperatures report
        model.xmtQ.put('M302 P1')   # enable cold extrusion
        time.sleep(0.1)    # allow linenum to get updated by transceiver
        t0 = time.time()            # get starttime for run()
        gui.after(10, run)          # start main event handler
        
def run():   
    global t0
    if time.time() - t0 > 2.0:  # update the gui once per x seconds
        t0 = time.time()
        # update positions panel:
        pos.update(model.pos)
        # update temperatures:
        e0tmp.setPV(model.tmp['T0:']['PV'])
        e0tmp.setSP(model.tmp['T0:']['SP'])
        e1tmp.setPV(model.tmp['T1:']['PV'])
        e1tmp.setSP(model.tmp['T1:']['SP'])
        bedtmp.setPV(model.tmp['B:']['PV'])
        bedtmp.setSP(model.tmp['B:']['SP'])
        if model.printing:
            # show progress bar
            status.txt.config(state = 'normal')
            status.txt.insert ('insert linestart', model.progress(model.curline, 
                                                                  model.filesize, 
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
    if not model.ready:
        gui.after(10, start)    # restart comms when needed
    else:
        gui.after(1000, run)


def die():
   transport.kill = True
   model.kill = True
   time.sleep(0.1)
   gui.destroy()               

        
#------------------------------------------------------------------------------    
# M A I N   P R O G R A M
#------------------------------------------------------------------------------    
        
if __name__ == '__main__':
    # creating root
    gui = ThemedTk(theme="black")    # equilux is nice too     
    gui.title('3D-O-Matic Marlinterface')
    gui.configure(bg='black')
    gui.style = themed_style.ThemedStyle()
    gui.protocol('WM_DELETE_WINDOW', die)

    try:
        # build the gui:
        status = textpanel.Textpanel(gui, ' System Status', h=7, w=40, sb=0)
        info = textpanel.Textpanel(gui, ' Info from Printer', h=15, w=90)
        dlgs = dialogpanel.Dialogpanel(gui, info, status)
        jog = jogpanel.Jogpanel(gui, status)
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
        
        # run the program:
        t0 = 0
        start()
        gui.mainloop()
        
    except KeyboardInterrupt:
        print('bye...')
        
    finally:
        transport.kill=True
        model.kill = True
