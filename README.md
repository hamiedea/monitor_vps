# monitor-vps

## Persiapan
``` bash
sudo apt-get update
sudo apt-get upgrade -y
sudo apt-get install python3-pip screen -y
```

## Buat direktori dan masuk
``` bash
mkdir monitor_vps
cd monitor_vps
```
## Buat file config.json
``` bash
nano config.json
```
## Buat file bot.py
``` bash
nano bot.py
``` 
## Instal library yang dibutuhkan
``` bash
pip3 install "python-telegram-bot[job-queue]"
```

## Jalankan bot di dalam 'screen`
``` bash
screen -S monitor
```

## Jalankan Program
``` bash
python3 bot.py
```
#

# OTOMATIS

## Buat direktori dan masuk
``` bash
mkdir monitor_vps
cd monitor_vps
```
###
