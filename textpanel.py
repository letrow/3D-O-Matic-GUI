#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Tue Mar  1 13:51:27 2022

@author: hschulz
"""
import tkinter as tk
from tkinter import ttk
from tkinter import scrolledtext
import model

class Textpanel(ttk.Frame):
    ''' A widget for displaying text.'''
    
    def __init__(self, master, caption, h, w, sb=1):
        ttk.Frame.__init__(self, master, height=h, width=w)
        self.master = master
        self.label = ttk.Label(self, text=caption)
        self.txt = tk.Text(self, height=h, width=w, wrap= 'word')
        self.sbar = tk.Scrollbar(self)

        self.label.grid(row=0, column=0, padx=4, pady=4, sticky='W')
        self.txt.grid (row=1, column=0, padx=4, pady=4, sticky='NSEW')
        if sb:
            self.sbar.grid(row=1, column=1, sticky='NSE')
            self.sbar['command'] = self.txt.yview
            self.txt['yscrollcommand'] = self.sbar.set
        self.txt.bind('<Return>', lambda event: self.send())
        
    def show(self, txt):
        ''' Show method is non-editable.'''
        self.txt.configure(state='normal')
        self.txt.insert('end', txt)
        self.txt.see( 'end')
        self.txt.configure(state='disabled')
        
    def send(self):
        ''' Only used in MDI panel to send text to printer.'''
        model.xmtQ.put(self.txt.get('1.0', 'end').upper().strip('\n'))
        self.txt.delete('1.0', 'end')
        