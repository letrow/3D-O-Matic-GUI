#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Mon Feb 21 18:54:04 2022

@author: hschulz
"""
#import tkinter as tk
from tkinter import ttk

import model



class Pospanel(ttk.Frame):
    ''' A widget for position indication.'''
   
    def __init__(self, master):
        ttk.Frame.__init__(self, master)
        self.master = master
        self.selectedAxisBtn = None   # selected axis button (!)
        
        self.xbtn = ttk.Button(self, text='X: ', style ='Unhomed.Axis.TButton',
                              command =lambda: self._select(self.xbtn))
        self.ybtn = ttk.Button(self, text='Y: ',style = 'Unhomed.Axis.TButton',
                              command = lambda: self._select(self.ybtn))
        self.zbtn = ttk.Button(self, text='Z: ',style = 'Unhomed.Axis.TButton',
                              command = lambda: self._select(self.zbtn))
        self.ebtn = ttk.Button(self, text='E: ',style = 'Homed.Axis.TButton')
        self.e0btn = ttk.Button(self, text='E0 ',style = 'Extr.Axis.TButton',
                                command = lambda: self._select(self.e0btn))
        self.e1btn = ttk.Button(self, text='E1 ',style = 'Extr.Axis.TButton',
                                command = lambda: self._select(self.e1btn))
        
        self.xbtn.grid(column=0, row=0, sticky='NSW', padx=4, pady=4)
        self.ybtn.grid(column=0, row=1, sticky='NSW', padx=4, pady=4)
        self.zbtn.grid(column=0, row=2, sticky='NSW', padx=4, pady=4)
        self.ebtn.grid(column=0, row=3, sticky='NSW', padx=4, pady=4)
        self.e0btn.grid(column=1, row=1, sticky='W', padx=4)
        self.e1btn.grid(column=1, row=2, sticky='W', padx=4)

        # configure styles specific for this module
        self.style = master.style   # styles defined centrally by theme in gui
        self.style.configure('Axis.TButton', 
            font=('Helvetica', 18, 'bold'))
        self.style.configure('Homed.Axis.TButton', 
            foreground='lightgreen')
        self.style.configure('Unhomed.Axis.TButton', 
            foreground='yellow')       
        self.style.map('Axis.TButton',          # map colors to state
            background=[('selected', 'red'),
                        ('pressed', 'grey'),
                        ('hover', 'darkgrey')])
        self.style.configure('Extr.Axis.TButton', # smaller font for extruders
            width=3, font=('Helvetica', 12, 'bold'))
        
    def update(self, pos):
        ''' Update the values (pos=[x,y,z,e0,e1]).'''
        x,y,z,e = pos[0:4:]
        self.xbtn.configure(text='X: {:>-8.2f}'.format(x))
        self.ybtn.configure(text='Y: {:>-8.2f}'.format(y))
        self.zbtn.configure(text='Z: {:>-8.2f}'.format(z))
        self.ebtn.configure(text='E: {:>-8.2f}'.format(e))
        self.xbtn.configure(style='Homed.Axis.TButton'
                            if 'X' in model.homed 
                            else 'Unhomed.Axis.TButton')
        self.ybtn.configure(style='Homed.Axis.TButton'
                            if 'Y' in model.homed 
                            else 'Unhomed.Axis.TButton')
        self.zbtn.configure(style='Homed.Axis.TButton'
                            if 'Z' in model.homed 
                            else 'Unhomed.Axis.TButton')
  
    def getAxis(self, btn):
        ''' Convert axis button to index for global use.'''
        axes = [self.xbtn, self.ybtn, self.zbtn, self.e0btn, self.e1btn]
        return axes.index(btn) if self.selectedAxisBtn else None
           
    def _select(self, axisBtn):
        ''' Turn previously selected axis off and select new axis. '''
        if axisBtn == self.selectedAxisBtn: # toggle if already on
            self.selectedAxisBtn=None
            axisBtn.state(['!selected'])
        else:
            if self.selectedAxisBtn: # turn off previous selection
                self.selectedAxisBtn.state(['!selected'])
            self.selectedAxisBtn=axisBtn
            axisBtn.state(['selected'])
        # copy to global model:
        model.selectedAxis = self.getAxis(axisBtn)
        if model.selectedAxis in (3,4): # 3 or 4: extruder 0 or 1 selected
            model.xmtQ.put('T'+ '01'[model.selectedAxis-3])
        
    def disable(self):
        ''' Disable all controls (could interfere with  printing).'''
        for btn in  (self.e0btn, self.e1btn):
            btn.config(state = 'disabled')

    def enable(self):
        ''' Enable all controls.'''
        for btn in  (self.e0btn, self.e1btn):
            btn.config(state = 'normal')
