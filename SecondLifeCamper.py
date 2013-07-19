from win32con import *
from win32gui import *
from time import sleep

class SecondLifeCamper:
    "Second Life Camper class"
    
    hWnd = 0        # Second Life window handle

    def __init__(self):
        "Constructor"
        
        self.getWindowHandle()
        if self.hWnd == 0:
            raise Exception, "Cannot find the Second Life window"

    def getWindowHandle(self):
        "Get the Second Life window handle"

        def EnumWindowProc(hWnd, self):
            if GetWindowText(hWnd) == "Second Life":
                self.hWnd = hWnd

        EnumWindows(EnumWindowProc, self)
        return self.hWnd

    def sendKey(self, keycode):
        "Send a single keystroke"
        
        SendMessage(self.hWnd, WM_KEYDOWN, keycode, 0)
        sleep(0.5)
        SendMessage(self.hWnd, WM_KEYUP, keycode, 0)
        sleep(0.5)

    def camp(self):
        "Camping routine"

        # Loop until the user hits Ctrl-C
        while 1:

            # Make a little pause so we don't use 100% CPU
            sleep(10)

            # Send a keystroke for "left arrow"
            self.sendKey(VK_LEFT)

            # Send a keystroke for "right arrow"
            self.sendKey(VK_RIGHT)


# when run from the commandline as a script, do this
if __name__ == "__main__":
    s = SecondLifeCamper()
    print "Camping..."
    s.camp()
