# -*- coding: utf-8 -*-
"""
Created on Wed Oct 30 19:38:45 2024

@author: grego
"""

import sys
from PyQt5.QtWidgets import QApplication, QMainWindow, QLabel, QPushButton, QVBoxLayout, QWidget, QHBoxLayout
from PyQt5.QtCore import Qt
import asyncio
from qasync import QEventLoop, asyncSlot
import main1


class ArmControlGUI(QMainWindow):
    def __init__(self, arm):
        super().__init__()
        self.arm = arm
        self.initUI()

    def initUI(self):
        self.setWindowTitle("Robotic Arm Load Control")
        self.setGeometry(300, 300, 400, 200)

        # Main widget
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        
        # Layout
        layout = QVBoxLayout(central_widget)

        # Load label to display current load
        self.load_label = QLabel("Current Load: 0.2 kg", self)
        self.load_label.setAlignment(Qt.AlignCenter)
        layout.addWidget(self.load_label)

        # Buttons for setting different load values
        button_layout = QHBoxLayout()

        # Define load values and create buttons for each
        load_values = [0.2, 1.0, 2.0, 3.0, 4.0, 5.0]  #loads in kg
        for load in load_values:
            button = QPushButton(f"{load} kg", self)
            button.clicked.connect(lambda _, l=load: self.set_load(l))
            button_layout.addWidget(button)

        layout.addLayout(button_layout)

    @asyncSlot()  # Marks this function as an asynchronous slot compatible with PyQt
    async def set_load(self, load_value):
        # Set the load in the arm asynchronously and update the label
        await self.arm.set_end_mass(load_value)  # Await if this is an async call
        self.load_label.setText(f"Current Load: {load_value:.1f} kg")
        print(f"Updated load to: {load_value:.1f} kg")

async def main():
   
    while True:
        print("Running background task...")
        await asyncio.sleep(1)

if __name__ == "__main__":
    app = QApplication(sys.argv)

    
    m1 = 0.5
    l1 = 0.5
    m2 = 0.5
    l2 = 0.5
    initial_end_mass = 0.5 # Initial end mass / load setting

    arm = main1.arm(m1,l1,m2,l2,initial_end_mass) 
    
    # Set up the GUI
    arm_control = ArmControlGUI(arm)
    arm_control.show()

    # Use QEventLoop to integrate asyncio with the PyQt event loop
    loop = QEventLoop(app)
    asyncio.set_event_loop(loop)

    with loop:
        loop.create_task(main())  # Start the background async task
        loop.run_forever()        # Start the event loop
