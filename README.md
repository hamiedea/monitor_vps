# MONITOR VPS
#
# IMPORTANT

> File `bot.py` dan `config.json` Hanya untuk instalasi **MANUAL**

> File `monitor.sh` Hanya untuk instalassi **OTOMATIS**

#

# INSTALASI OTOMATIS

## Buat direktori dan masuk
``` bash
mkdir monitor_vps
cd monitor_vps
```
## Download file
``` bash
wget https://raw.githubusercontent.com/hamiedea/monitor_vps/main/monitor.sh
```
## Berikan izin eksekusi pada file
``` bash
chmod +x monitor.sh
```
## Jalankan skrip
``` bash
./monitor.sh
```
#


# INSTALASI MANUAL
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
## Buat File Config
``` bash
nano config.json
```
Copy Dan Masukan Token Bot Anda
``` bash
{
  "BOT_TOKEN": "MASUKAN_TOKEN_BOT_ANDA",
  "MONITOR_INTERVAL_SECONDS": 120
}
```

## Download File Bot nya
``` bash
wget https://raw.githubusercontent.com/hamiedea/monitor_vps/main/bot.py
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

