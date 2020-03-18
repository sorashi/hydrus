@echo off
echo The build script requires that you have venv, wget and 7z installed and that Python is executable under py
call prepare.bat
call env\Scripts\activate.bat
set ffmpegurl=https://ffmpeg.zeranoe.com/builds/win64/static/ffmpeg-20200315-c467328-win64-static.zip
set ffmpegzip=".\build\ffmpeg-static.zip"
if not exist .\bin\ffmpeg.exe (
    if not exist %ffmpegzip% wget %ffmpegurl% -O %ffmpegzip%
    7z e %ffmpegzip% -obin ffmpeg.exe -r
)
REM pyinstaller can't export multiple exe's easily until this https://github.com/pyinstaller/pyinstaller/issues/1527 is fixed
REM for now, we build both client and server and then merge them using xcopy
pyinstaller server.py -i static\hydrus.ico
pyinstaller -w client.pyw -i static\hydrus.ico --add-binary bin;bin --add-data static;static
cd dist
REM /e copies all subdirectories even if empty, /d copies only newer files, /y skips overwrite confirmations
xcopy /e /d /y server client
move client hydrus
7z a hydrus.zip hydrus\