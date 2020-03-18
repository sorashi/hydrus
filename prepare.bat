if not exist env\Scripts\activate.bat py -m venv env
call env\Scripts\activate.bat
pip install beautifulsoup4 chardet html5lib lxml nose numpy opencv-python-headless six Pillow psutil PyOpenSSL PyYAML requests Send2Trash service_identity twisted lz4 pylzma
pip install qtpy PySide2
pip install mock httmock
pip install pyinstaller