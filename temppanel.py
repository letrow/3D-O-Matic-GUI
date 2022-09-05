#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Mon Feb 21 18:54:04 2022

@author: hschulz
"""
import tkinter as tk
from tkinter import ttk
import data

class Temppanel(ttk.Frame):
    ''' A widget for temperature controllers.'''
   
    def __init__(self, master, name, extId, gcode):
        ttk.Frame.__init__(self, master)    # instantiate our super class
        self.name = name    # identifier of the controller
        self.extId = extId  # extruder selector (if any)
        self.setPoint = 0   # set point value
        self.procVal = 0    # process value
        self.scale = 300    # scale
        self.tol = 2        # tolerance within which the LED turns on
        self.lock = False   # avoid multiple popups
        self.gcode = gcode  # command to set SP in printer (M104 or M140)
        
        self.cv = tk.Canvas(self, width=236, height=50, 
                            bd=1, highlightt=0, bg='black')
        self.cv.create_rectangle( 2, 14, 200, 36, 
                                 fill='gray', outline='white')
        self.cv.create_polygon(-8, 0, 8, 0, 0, 13, 
                                 tags='arrow', fill='white', outline='navy')
        self.cv.create_rectangle(2, 15, 0, 35, 
                                 tags='bar', fill='navy', width=0)    
        self.cv.create_text(190, 45, font=('Helvetica', 8),
                                 fill='white', text=self.scale, tags='scale')
        self.cv.create_text(5, 45, font=('Helvetica', 8),
                                 fill='white', text=0)
        self.cv.create_text(100, 25, font=('Helvetica', 12, 'bold'),
                                 fill='white', text=0, tags='perc')
        self.cv.create_oval(212, 12, 212+24, 36, fill='gray') # bezel only
        self.cv.create_oval(215, 15, 212+21, 33, fill='red', tags='led')
        self.cv.bind('<Button-1>', self.setPopup)

        self.lb1 = ttk.Label(self, text = self.name)
        self.lb2 = ttk.Label(self, text = 'Set Point: --')
        
        self.lb1.grid(column=0, row=0, sticky='W', padx=5, pady=4)
        self.lb2.grid(column=1, row=0, sticky='E', padx=5, pady=4)
        self.cv.grid(column=0, row=1, columnspan=2, padx=5, pady=4)
       
    def setScale(self, value):
        self.scale = value
        self.cv.itemconfig('scale', text=value)
        
    def setSP(self, value):
        self.setPoint = value
        self.lb2.configure(text='Set Point: {} ⁰C'.format(value))
        pos = value*200 //self.scale
        self.cv.coords('arrow', pos-8, 2, pos+8, 2, pos, 13)
        self.setTol(self.tol)
 
    def setPV(self, value):
        self.procVal = value
        self.cv.coords('bar', 3, 15, 
            min(value*200/self.scale, 200), 35)
        self.cv.itemconfig('perc',
            text="- -" if value < 0 else "{:3.1f} ⁰C".format(value))
        self.setTol(self.tol)   # update LED status
  
    def setTol(self, value):
        self.tol = value
        self.cv.itemconfig('led', 
            fill='lightgreen' if abs(self.procVal - self.setPoint) < value 
                              else 'red')
    
    def setPopup(self, *args):
        ''' pop up the set temps window to set SP.'''
        if self.lock:   # allow only one instance
            return
        self.lock = True
        popup = tk.Toplevel(self, bg='black')
        popup.title(self.name)
        popup.protocol('WM_DELETE_WINDOW', lambda: self.shutdown(popup))

        label = ttk.Label(popup, text=self.name+'Set Point (⁰C):')
        entry = ttk.Entry(popup, width=12)
        okBtn = ttk.Button(popup, width=8, 
                           command=lambda: self.setTemp(entry.get(), popup), 
                           text='OK')
        cancelBtn = ttk.Button(popup, command= lambda: self.shutdown(popup), 
                               width=8, text='Cancel')
        popup.bind('<Return>', lambda event: self.setTemp(entry.get(), popup))
        
        label.grid(row=0, column=0, columnspan=3, pady=10, padx=5)
        entry.grid(row=1, column=2, columnspan=2, pady=10, padx=5)
        okBtn.grid(row=2, column=1, pady=10, padx=5)
        cancelBtn.grid(row=2, column=2, pady=10, padx=5)
        entry.focus_set()

    def setTemp(self, val, obj):  
        try:
            val = float(val)
        except ValueError:
            print(val, 'is not a valid temperaturee')
        else:
            self.setSP(val)
            if self.extId:
                data.xmtQ.put(self.extId)  # select extruder (if any)
            data.xmtQ.put('{} S{}'.format(self.gcode, float(self.setPoint)))
        finally:
            self.shutdown(obj)

    def shutdown(self, obj):
        self.lock = False
        obj.destroy()
