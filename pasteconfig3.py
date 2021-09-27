#!/usr/bin/env python

import sys
from PyQt4 import QtCore, QtGui, uic
import paramiko
import re
import time

#Defining the ui file to use with pyqt
qtPasteConfigurationUIFile = "ui/PasteConfiguration.ui"

#Defining the gui environment with the ui file
Ui_MainWindow, QtBaseClass = uic.loadUiType(qtPasteConfigurationUIFile)

TIMEOUT = 10

#Class to color the terminal output
class bcolors:
    HEADER = '\033[95m'
    OKBLUE = '\033[94m'
    OKGREEN = '\033[92m'
    WARNING = '\033[93m'
    FAIL = '\033[91m'
    ENDC = '\033[0m'
    BOLD = '\033[1m'
    UNDERLINE = '\033[4m'


class Progress(QtCore.QThread):
    #Class to run in another thread
    #Signals defined, one for progress bar and the other one for status info
    notifyProgress = QtCore.pyqtSignal(int, str)
    notifyStatus = QtCore.pyqtSignal(str)

    def __init__(self, ip=None, host=None, username=None, password=None, delay=None, commands=None):
        #Receiving all the data from the other class
        QtCore.QThread.__init__(self)
        self.ip = ip
        self.host = host
        self.username = username
        self.password = password
        self.delay = delay
        self.commands = commands

    def recv_buffer(self, conn, stop_string):
        """
        Function created to process and get the received data from teh ssh connection
        :param conn: The ssh client connection
        :param stop_string: The stop string, basically the string to wait to stop receiving the buffer
        :return: receive_buffer is the buffer received from the ssh command
        """
        receive_buffer = ""
        # Creating the stop string, removing domain from hostname
        m = re.search('(.+?)\.', stop_string)
        if m:
            stop_string = m.group(1) + '#'
        else:
            stop_string = '#'
        i = 0
        while not (stop_string in receive_buffer):
            # Flush the receive buffer
            try:
                receive_buffer += conn.recv(1024)
            except Exception as e:
                if type(e).__name__ == 'timeout':
                    i += 1
                    if i == 2:
                        print(bcolors.FAIL + "***********Timeout receiving buffer..." + bcolors.ENDC)
                        return receive_buffer + '\n***TIMEOUT ERROR***'
                else:
                    print(bcolors.FAIL + "***********Problem receiving data from {}...".format(
                        stop_string) + bcolors.ENDC)
                    print(bcolors.FAIL + 'Error: {}'.format(e.message) + bcolors.ENDC)
        return receive_buffer

    def run(self):
        """
        Function to connect to the devices via SSH
        """
        self.notifyProgress.emit(0,'...')

        # Creating the SSH CLient object
        ssh = paramiko.SSHClient()
        # Do not stop if the ssh key is not in memory
        ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        # Connecting....
        try:
            self.notifyStatus.emit("Connecting...")
            ssh.connect(self.ip, username=self.username, password=self.password, timeout=TIMEOUT)
        except Exception as e:
            self.notifyStatus.emit("Problem connecting...")
            print(bcolors.FAIL + "*****************Problem Connecting to {}...".format(self.host) + bcolors.ENDC)
            print(bcolors.FAIL + "*****************Error: {}".format(e.message) + bcolors.ENDC)
        else:
            self.notifyStatus.emit("Connected...")
            # Invoke shell
            remote_conn = ssh.invoke_shell()
            remote_conn.settimeout(TIMEOUT)
            dummy = self.recv_buffer(remote_conn, self.host)
            remote_conn.send('enable\n')
            dummy = self.recv_buffer(remote_conn, self.host)
            remote_conn.send('configure terminal\n')
            dummy = self.recv_buffer(remote_conn, self.host)
            i = 0
            self.notifyStatus.emit("Sending Commands ...")
            for command in self.commands:
                self.notifyProgress.emit(int(i/float(len(self.commands))*100), command)
                remote_conn.send(str(command) + '\n')
                dummy = self.recv_buffer(remote_conn, self.host)
                i += 1
                self.notifyProgress.emit(int(i/float(len(self.commands))*100), command)
                time.sleep(self.delay)

            remote_conn.send('end\n')
            self.notifyStatus.emit("Connection Closed ...")
            dummy = self.recv_buffer(remote_conn, self.host)
            ssh.close()


class MyApp(QtGui.QMainWindow, Ui_MainWindow):
    # PyQT App class
    def __init__(self):
        #definition of the main window
        QtGui.QMainWindow.__init__(self)
        Ui_MainWindow.__init__(self)
        self.setupUi(self)

        #Matching the events to functions
        self.plainTextEditCommands.textChanged.connect(self.FieldTextChanged)
        self.lineEditHostname.textChanged.connect(self.FieldTextChanged)
        self.lineEditUsername.textChanged.connect(self.FieldTextChanged)
        self.lineEditPassword.textChanged.connect(self.FieldTextChanged)
        self.lineEditDelay.textChanged.connect(self.FieldTextChanged)
        self.lineEditIp.textChanged.connect(self.FieldTextChanged)

        #Creating the thread Progress with different signals
        self.progressView = Progress()
        self.progressView.notifyProgress.connect(self.onProgress)
        self.progressView.notifyStatus.connect(self.onStatus)

        #Matching the finishing of the thread with a function
        self.progressView.finished.connect(self.threadDone)

        # Matching the button click event with a function
        self.pushButtonSend.clicked.connect(self.sendData)

    def onStatus(self, msg):
        """
        Function to update the status if the label to add feedback to the user
        :param msg: Message to display
        :return:
        """
        self.labelStatus.setText(msg)

    def onProgress(self, i, com):
        """
        Function to update the progress of teh commands sent
        :param i: Percentage
        :param com: Command being sent
        :return:
        """
        self.progressBar.setValue(i)
        self.labelCommand.setText(com)

    def threadDone(self):
        """
        Function to do clean up the GUI after the thread is done
        :return:
        """
        self.labelSendingCommand.setEnabled(False)
        self.labelCommand.setEnabled(False)
        self.progressBar.setEnabled(False)
        self.lineEditUsername.setText("")
        self.lineEditPassword.setText("")
        QtGui.QMessageBox.question(self, "Complete", "All commands sent successfully!!!", QtGui.QMessageBox.Ok)
        self.labelStatus.setText("Waiting for Input...")

    def sendData(self):
        """
        Function that will run as soon as the Send button was clicked and starts the parallel thread
        :return:
        """
        self.progressView.ip = str(self.lineEditIp.text())
        self.progressView.host = str(self.lineEditHostname.text())
        self.progressView.username = str(self.lineEditUsername.text())
        self.progressView.password = str(self.lineEditPassword.text())
        self.progressView.delay = int(self.lineEditDelay.text()) / 1000
        self.progressView.commands = self.plainTextEditCommands.toPlainText().split('\n')

        self.labelSendingCommand.setEnabled(True)
        self.labelCommand.setEnabled(True)
        self.progressBar.setEnabled(True)
        self.progressView.start()

    def FieldTextChanged(self):
        """
        Function to check that all the fields where filled before enabling the Send Button
        :return:
        """
        if self.plainTextEditCommands.toPlainText() != '' and self.lineEditHostname.text() != '' and \
                        self.lineEditUsername.text() != '' and self.lineEditPassword.text() != '' and \
                        self.lineEditDelay.text() != '' and self.lineEditIp.text() != '':

            self.pushButtonSend.setEnabled(True)
            self.labelStatus.setText("Ready to connect!!!")
        else:
            self.pushButtonSend.setEnabled(False)


if __name__ == "__main__":
    #Create The pyQT application
    app = QtGui.QApplication(sys.argv)
    window = MyApp()
    window.show()
    sys.exit(app.exec_())
