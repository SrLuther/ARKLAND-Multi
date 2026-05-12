import sys
import os

# Garante que o diretório raiz esteja no path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from src.app import ARKLandMultiApp

if __name__ == "__main__":
    app = ARKLandMultiApp()
    app.mainloop()
