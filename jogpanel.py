#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Wed Feb 23 17:39:53 2022

@author: hschulz
"""
import tkinter as tk
from tkinter import ttk
import data

class Jogpanel(ttk.Frame):
    ''' A widget for jogging the steppers.'''
    mmSteps = [ '0.1 mm', '1 mm', '10 mm', '100 mm', 'continuous']
    steps = [0.1, 1, 10, 100, -1]
    axes = ['X', 'Y', 'Z', 'E', 'E']

    
    def __init__(self, master, status):
        ttk.Frame.__init__(self, master)
        self.master = master
        self.status = status
        self.stepsize = tk.IntVar(self, 2)  # default to 10 mm
        self.stepsize.trace('w', self.setmm)
        self.lock=False
        self.zZero=0
        self.ispressed = False
        
        self.stepbtn = ttk.Menubutton(self, width=10,
                            text=Jogpanel.mmSteps[self.stepsize.get()])
        self.upbtn = ttk.Button(self, #command=lambda: self.doJog(1), 
                            text = '+', style='Arrow.TButton')
        self.homebtn = ttk.Button(self, command=lambda: self.doHome(),
                            text = 'home', style='Home.Arrow.TButton')
        self.downbtn = ttk.Button(self, #command=lambda: self.doJog(-1),
                                  text = '-', style='Arrow.TButton')
        self.toffbtn = ttk.Button(self, command=self.touchoff, 
                                      text = 'Touch Off', width=10)
        self.columnconfigure(0, weight=2)           
        self.columnconfigure(1, weight=3)           
        self.columnconfigure(2, weight=2)           

        self.stepbtn.grid(column=0, row=0, columnspan=3, padx=4, pady=4, sticky='EW')
        self.upbtn.grid(column=0, row=1, rowspan=1, padx=4,pady=0, sticky='W')
        self.homebtn.grid(column=1, row=1, rowspan=1, padx=4,pady=0, sticky='EW')
        self.downbtn.grid(column=2, row=1, rowspan=1, padx=4,pady=0, sticky='E')
        self.toffbtn.grid(column=0, row=2, columnspan=3, padx=4,pady=4, sticky='EW')

        # create drop down menu for stepsize:
        self.mmMenu = tk.Menu(self.stepbtn, tearoff=0)
        for i, txt in enumerate(Jogpanel.mmSteps):
            self.mmMenu.add_radiobutton(
                value = i,
                label = txt,
                variable = self.stepsize)
        # associate mmMenu with the step button:
        self.stepbtn["menu"] = self.mmMenu

        self.upbtn.bind('<Button-1>', self.pressedUp)
        self.upbtn.bind('<ButtonRelease-1>', self.released )
        self.downbtn.bind('<Button-1>', self.pressedDown)
        self.downbtn.bind('<ButtonRelease-1>', self.released )

            
        # configure styles specific for this module
        self.style = master.style   # styles defined centrally by theme in gui
        self.style.configure('Arrow.TButton', width=2, height=2,
            font=('Helvetica', 12, 'bold'))
        
        self.style.configure('Home.Arrow.TButton', width=8)
   
    def setmm(self, *args):
        '''call back for stepsize menubutton. '''
        self.stepbtn.config(text=Jogpanel.mmSteps[self.stepsize.get()]) 
    
    def touchoff(self):
        ''' pop up the touch off window to set work coordinates.'''
        if self.lock:   # allow only one instance
            return
        self.lock = True
        toff = tk.Toplevel(self, bg='black')
        toff.title('Touch Off')
        toff.protocol('WM_DELETE_WINDOW', lambda: self.shutdown(toff))

        label = ttk.Label(toff, text='Set Z coordinate relative to bed:')
        entry = ttk.Entry(toff, width=12)
        okBtn = ttk.Button(toff, width=8, 
                           command=lambda: self.setZ(entry.get(), toff), 
                           text='OK')
        cancelBtn = ttk.Button(toff, command= lambda: self.shutdown(toff), 
                               width=8, text='Cancel')
        toff.bind('<Return>', lambda event: self.setZ(entry.get(), toff))
        
        label.grid(row=0, column=0, columnspan=3, pady=10, padx=5)
        entry.grid(row=1, column=2, columnspan=2, pady=10, padx=5)
        okBtn.grid(row=2, column=1, pady=10, padx=5)
        cancelBtn.grid(row=2, column=2, pady=10, padx=5)
        entry.focus_set()

    def setZ(self, val, obj):  
        try:
            val = float(val)
        except ValueError:
            print(val, 'is not a valid Z-value')
        else:
            self.zZero = val
            data.xmtQ.put('G92 Z{}'.format(val))
            data.homed.add('Z')
        finally:
            self.shutdown(obj)
            
    def doJog(self, dir):
        ''' Issue jog command to printer using current axis and stepsize. '''
        if data.selectedAxis == None:
            print('No axis selected')
            return
        
        mm = Jogpanel.steps[self.stepsize.get()]
        axis = Jogpanel.axes[data.selectedAxis]
        
        # set relative coords:
        cmd = 'G91'
        data.xmtQ.put(cmd)
        if axis == 'E':  # extruder 
            data.xmtQ.put('M302 P1')   # enable cold extrusion
        if mm > 0: # single action mode
            cmd = 'G0 {}{}'.format(axis, mm*dir)
            data.xmtQ.put(cmd)
        else:   # continuous mode
            self.cmd = 'G0 {}{}'.format(axis, dir)
            self.rippleJog()
            
    def rippleJog(self):
        data.xmtQ.put(self.cmd)
        if self.ispressed:
            self.master.after(100, self.rippleJog)

    def doHome(self):
        ''' Issue home command for selected axis to printer. '''
        if data.selectedAxis == None:
            self.status.show('No axis selected\n')
            return
        axis = Jogpanel.axes[data.selectedAxis]
        if 'T'in axis:  # we don't home the extruder steppers
            return
        cmd = 'G28 {}'.format(axis if not axis == 'Z' else 'R10 Z')
        data.xmtQ.put(cmd)
        data.homed.add(axis)

    def pressedUp(self, *args):
        self.ispressed = True
        self.doJog(1)
        
    def pressedDown(self, *args):
        self.ispressed = True
        self.doJog(-1)

    def released(self, *args):
        self.ispressed = False               

    def shutdown(self, obj):
        self.lock = False
        obj.destroy()
        
    def disable(self):
        ''' Disable all controls (avoids homing while printing).'''
        for btn in  (self.upbtn, self.homebtn, self.downbtn, self.toffbtn):
            btn.config(state = 'disabled')

    def enable(self):
        ''' Enable all controls.'''
        for btn in  (self.upbtn, self.homebtn, self.downbtn, self.toffbtn):
            btn.config(state = 'normal')
